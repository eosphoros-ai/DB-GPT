"""Transport tests for the owner-aware session file API.

The storage seam is a stub built directly on the real ``SessionFileDao``
(Task 2) and ``SessionFileInspector`` (Task 3) so the transport contract is
exercised against the same DAO scoping rules and bounded inspection behavior
the final registry will orchestrate later.
"""

import hashlib
import importlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from starlette.datastructures import UploadFile as StarletteUploadFile

from dbgpt.storage.metadata import db
from dbgpt_serve.session_file.api import endpoints as endpoints_module
from dbgpt_serve.session_file.config import ServeConfig
from dbgpt_serve.session_file.domain import (
    FileScope,
    SessionFilePrivateRecord,
    SessionFileStatus,
)
from dbgpt_serve.session_file.inspector import SessionFileInspector
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401

PREFIX = "/api/v1/agent/files"
ALICE = {"user-id": "alice"}
BOB = {"user-id": "bob"}
CSV_CONTENT = b"colA,colB\n1,2\n"


class _StubSessionFileService:
    """DAO+inspector backed stub standing in for the future registry.

    Implements the same protocol the registry will implement; only upload
    orchestration (quota locks, storage compensation, materialization) is
    intentionally absent here.
    """

    def __init__(self, storage_root: Path):
        self._root = storage_root
        self._root.mkdir(parents=True, exist_ok=True)
        self._dao = SessionFileDao()
        base = SessionFileInspector()
        # Custom parser bindings keep every inspection on the trusted in-thread
        # path, avoiding per-call subprocess spawns in transport tests.
        self._inspector = SessionFileInspector(
            optional_import=importlib.import_module,
            parsers={
                ".csv": base._parse_delimited,
                ".tsv": base._parse_delimited,
                ".json": base._parse_json,
                ".jsonl": base._parse_json,
                ".txt": base._parse_text,
                ".md": base._parse_text,
            },
        )
        self._blobs: Dict[str, Path] = {}
        self.ingest_calls: List[str] = []
        self._counter = 0

    def ingest(
        self,
        *,
        owner_id: str,
        session_id: str,
        display_name: str,
        media_type: Optional[str],
        stream,
        size_bytes: int,
    ) -> SessionFilePrivateRecord:
        content = stream.read()
        self._counter += 1
        file_id = f"sf_test_{self._counter:04d}"
        # Keep the original suffix: the inspector dispatches by extension.
        suffix = Path(display_name).suffix.lower()
        blob_path = self._root / f"{file_id}{suffix}"
        blob_path.write_bytes(content)
        self._blobs[file_id] = blob_path
        self.ingest_calls.append(display_name)
        scope = FileScope(owner_id, session_id=session_id)
        result = self._inspector.inspect(blob_path, media_type)
        inspection_json = json.dumps(
            {"preview": result.preview, "truncated": result.truncated},
            default=str,
        )
        self._dao.create(
            {
                "file_id": file_id,
                "owner_id": owner_id,
                "session_id": session_id,
                "task_id": None,
                "display_name": display_name,
                "storage_uri": f"stub://session-files/{file_id}",
                "media_type": result.media_type,
                "file_kind": result.kind,
                "size_bytes": size_bytes,
                "sha256": hashlib.sha256(content).hexdigest(),
                "ordinal": len(self._dao.list_by_scope(scope)),
                "status": result.status.value,
                "inspection_json": inspection_json,
                "error_code": result.error_code,
                "error_message": result.error_message,
                "source_file_id": None,
            }
        )
        persisted = self._dao.get_private_file_by_id(file_id, scope)
        assert persisted is not None
        return persisted

    def list_files(
        self, *, owner_id: str, session_id: str
    ) -> List[SessionFilePrivateRecord]:
        scope = FileScope(owner_id, session_id=session_id)
        return [
            self._dao.get_private_file_by_id(item.file_id, scope)
            for item in self._dao.list_by_scope(scope)
        ]

    def get_file(
        self, *, owner_id: str, session_id: str, file_id: str
    ) -> Optional[SessionFilePrivateRecord]:
        return self._dao.get_private_file_by_id(
            file_id, FileScope(owner_id, session_id=session_id)
        )

    def open_download(
        self, *, owner_id: str, session_id: str, file_id: str
    ) -> Optional[Tuple]:
        record = self.get_file(
            owner_id=owner_id, session_id=session_id, file_id=file_id
        )
        if record is None:
            return None
        return self._blobs[file_id].open("rb"), record

    def delete_file(self, *, owner_id: str, session_id: str, file_id: str) -> bool:
        scope = FileScope(owner_id, session_id=session_id)
        deleted = self._dao.delete_by_file_id(file_id, scope)
        if deleted:
            self._blobs.pop(file_id, None)
        return deleted


@pytest.fixture(autouse=True)
def _isolate_module_state():
    endpoints_module._reset_endpoints()
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    yield
    endpoints_module._reset_endpoints()


@pytest.fixture()
def transport(tmp_path):
    service = _StubSessionFileService(tmp_path / "blobs")
    config = ServeConfig(
        max_files_per_upload=2,
        max_file_bytes=64,
        max_upload_bytes=96,
        max_owner_bytes=512,
        upload_concurrency_advice=3,
        upload_chunk_bytes=8,
        upload_spool_bytes=32,
        download_chunk_bytes=8,
        max_file_name_bytes=32,
    )
    app = FastAPI()
    app.include_router(endpoints_module.router, prefix=PREFIX)
    endpoints_module.init_endpoints(MagicMock(), service, config)
    return TestClient(app), service


@pytest.fixture()
def client(transport):
    return transport[0]


def _csv_file(name="report.csv", content=CSV_CONTENT, media="text/csv"):
    return ("files", (name, content, media))


def _upload(client, files=None):
    files = [_csv_file()] if files is None else files
    return client.post(
        PREFIX, data={"session_id": "conv-1"}, files=files, headers=ALICE
    )


def _assert_error(response, status_code, err_code):
    assert response.status_code == status_code, response.text
    payload = response.json()
    assert payload["success"] is False
    assert payload["err_code"] == err_code
    return payload


# ---------------------------------------------------------------------------
# Route surface
# ---------------------------------------------------------------------------


def test_all_contract_routes_are_registered():
    app = FastAPI()
    app.include_router(endpoints_module.router, prefix=PREFIX)

    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    expected = {
        (PREFIX, "POST"),
        (PREFIX, "GET"),
        (PREFIX + "/capabilities", "GET"),
        (PREFIX + "/{file_id}", "GET"),
        (PREFIX + "/{file_id}", "DELETE"),
        (PREFIX + "/{file_id}/preview", "GET"),
        (PREFIX + "/{file_id}/download", "GET"),
    }
    assert expected <= routes


# ---------------------------------------------------------------------------
# Upload contract
# ---------------------------------------------------------------------------


def test_upload_single_csv_returns_public_manifest(client, transport):
    _, service = transport

    response = _upload(client)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    (item,) = payload["data"]
    assert set(item) == {
        "file_id",
        "name",
        "size",
        "media_type",
        "kind",
        "status",
        "ordinal",
        "error_code",
    }
    assert item["file_id"].startswith("sf_")
    assert item["name"] == "report.csv"
    assert item["size"] == len(CSV_CONTENT)
    assert item["media_type"] == "text/csv"
    assert item["kind"] == "table"
    assert item["status"] == "ready"
    assert item["ordinal"] == 0
    assert item["error_code"] is None
    assert service.ingest_calls == ["report.csv"]


def test_upload_multiple_files_preserves_request_order(client):
    files = [
        _csv_file("first.csv", b"a\n1\n"),
        _csv_file("second.csv", b"b\n2\n"),
    ]

    response = _upload(client, files=files)

    assert response.status_code == 200, response.text
    items = response.json()["data"]
    assert [item["name"] for item in items] == ["first.csv", "second.csv"]
    assert [item["ordinal"] for item in items] == [0, 1]
    assert len({item["file_id"] for item in items}) == 2


def test_upload_requires_at_least_one_file(client):
    response = client.post(PREFIX, data={"session_id": "conv-1"}, headers=ALICE)

    _assert_error(response, 400, "EMPTY_FILE_UPLOAD")


def test_upload_rejects_more_files_than_capability(client, transport):
    _, service = transport
    files = [_csv_file("a.csv"), _csv_file("b.csv"), _csv_file("c.csv")]

    response = _upload(client, files=files)

    _assert_error(response, 400, "TOO_MANY_FILES")
    assert service.ingest_calls == []


def test_upload_rejects_oversized_file(client, transport):
    _, service = transport
    files = [_csv_file("big.csv", b"z" * 65)]

    response = _upload(client, files=files)

    _assert_error(response, 413, "FILE_TOO_LARGE")
    assert service.ingest_calls == []


def test_upload_rejects_aggregate_over_limit_before_persisting(client, transport):
    _, service = transport
    files = [_csv_file("a.csv", b"x" * 50), _csv_file("b.csv", b"y" * 50)]

    response = _upload(client, files=files)

    _assert_error(response, 413, "REQUEST_TOO_LARGE")
    assert service.ingest_calls == []


def test_upload_rejects_empty_file(client, transport):
    _, service = transport

    response = _upload(client, files=[_csv_file(content=b"")])

    _assert_error(response, 400, "EMPTY_FILE")
    assert service.ingest_calls == []


def test_upload_requires_session_id(client):
    response = client.post(PREFIX, files=[_csv_file()], headers=ALICE)

    _assert_error(response, 400, "MISSING_SESSION_ID")


def test_upload_rejects_blank_session_id(client):
    response = client.post(
        PREFIX, data={"session_id": "   "}, files=[_csv_file()], headers=ALICE
    )

    _assert_error(response, 400, "INVALID_SESSION_ID")


def test_upload_rejects_overlong_display_name(client):
    files = [_csv_file(name="n" * 40 + ".csv")]

    response = _upload(client, files=files)

    _assert_error(response, 400, "FILE_NAME_TOO_LONG")


def test_upload_reads_files_in_bounded_chunks(client, monkeypatch):
    reads = []
    # FastAPI form parsing instantiates starlette UploadFile objects.
    original_read = StarletteUploadFile.read

    async def spy_read(self, size=-1):
        reads.append(size)
        assert size is not None and size > 0, "unbounded read detected"
        return await original_read(self, size)

    monkeypatch.setattr(StarletteUploadFile, "read", spy_read)

    response = _upload(client, files=[_csv_file(content=b"a,b\n" * 10)])

    assert response.status_code == 200, response.text
    assert reads
    assert all(size == 8 for size in reads)


def test_upload_with_blank_owner_falls_back_to_shared_owner(client):
    response = client.post(
        PREFIX,
        data={"session_id": "conv-1"},
        files=[_csv_file()],
        headers={"user-id": "   "},
    )

    assert response.status_code == 200, response.text
    shared = client.get(PREFIX, params={"session_id": "conv-1"})
    assert [item["file_id"] for item in shared.json()["data"]] == [
        response.json()["data"][0]["file_id"]
    ]


def test_client_supplied_owner_fields_are_ignored(client):
    response = client.post(
        PREFIX + "?owner_id=bob&user_name=bob",
        data={"session_id": "conv-1", "owner": "bob"},
        files=[_csv_file()],
        headers=ALICE,
    )

    assert response.status_code == 200, response.text
    bob_list = client.get(PREFIX, params={"session_id": "conv-1"}, headers=BOB)
    alice_list = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)
    assert bob_list.json()["data"] == []
    assert len(alice_list.json()["data"]) == 1


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------


def test_capabilities_expose_server_owned_limits(client):
    response = client.get(PREFIX + "/capabilities", headers=ALICE)

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["max_files_per_upload"] == 2
    assert data["max_file_bytes"] == 64
    assert data["max_upload_bytes"] == 96
    assert data["max_owner_bytes"] == 512
    assert data["upload_concurrency"] == 3
    assert ".csv" in data["supported_extensions"]


# ---------------------------------------------------------------------------
# Auth, owner isolation and scope isolation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "suffix",
    ["", "/capabilities", "/sf_x", "/sf_x/preview", "/sf_x/download"],
)
def test_get_endpoints_with_blank_owner_fall_back_to_shared_owner(client, suffix):
    response = client.get(
        f"{PREFIX}{suffix}",
        params={"session_id": "conv-1"},
        headers={"user-id": "  "},
    )

    # Anonymous mode: a blank header maps to the shared "001" owner, so
    # capabilities/list return success and file-scoped lookups are 404-ish
    # for files that were never stored under "001".
    if suffix in ("", "/capabilities"):
        assert response.status_code == 200, response.text
        assert response.json()["success"] is True
    else:
        assert response.status_code == 404, response.text
        assert response.json()["success"] is False


def test_delete_with_blank_owner_uses_shared_owner_scope(client):
    response = client.delete(
        f"{PREFIX}/sf_x?session_id=conv-1", headers={"user-id": " "}
    )

    assert response.status_code == 404, response.text
    assert response.json()["success"] is False


def test_list_is_ordered_and_owner_scoped(client):
    files = [_csv_file("a.csv", b"a\n1\n"), _csv_file("b.csv", b"b\n2\n")]
    _upload(client, files=files)

    alice = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)
    assert [item["name"] for item in alice.json()["data"]] == ["a.csv", "b.csv"]
    assert [item["ordinal"] for item in alice.json()["data"]] == [0, 1]

    bob = client.get(PREFIX, params={"session_id": "conv-1"}, headers=BOB)
    assert bob.json()["data"] == []

    other_session = client.get(PREFIX, params={"session_id": "conv-2"}, headers=ALICE)
    assert other_session.json()["data"] == []


def test_detail_is_owner_and_scope_constrained(client):
    created = _upload(client).json()["data"][0]
    url = f"{PREFIX}/{created['file_id']}"

    ok = client.get(url, params={"session_id": "conv-1"}, headers=ALICE)
    assert ok.status_code == 200
    assert ok.json()["data"]["file_id"] == created["file_id"]

    foreign = client.get(url, params={"session_id": "conv-1"}, headers=BOB)
    missing = client.get(
        f"{PREFIX}/sf_missing", params={"session_id": "conv-1"}, headers=ALICE
    )
    other_session = client.get(url, params={"session_id": "conv-2"}, headers=ALICE)
    for response in (foreign, missing, other_session):
        _assert_error(response, 404, "SESSION_FILE_NOT_FOUND")
    # Non-enumerating: foreign files look identical to missing ones.
    assert foreign.json()["err_msg"] == missing.json()["err_msg"]


def test_task_scoped_records_are_invisible_to_session_endpoints(client):
    dao = SessionFileDao()
    dao.create(
        {
            "file_id": "sf_task_owned",
            "owner_id": "alice",
            "session_id": None,
            "task_id": "task-1",
            "display_name": "frozen.csv",
            "storage_uri": "stub://session-files/sf_task_owned",
            "media_type": "text/csv",
            "file_kind": "table",
            "size_bytes": 3,
            "sha256": "b" * 64,
            "ordinal": 0,
            "status": SessionFileStatus.READY.value,
            "inspection_json": None,
            "error_code": None,
            "error_message": None,
            "source_file_id": "sf_source_session",
        }
    )

    detail = client.get(
        f"{PREFIX}/sf_task_owned", params={"session_id": "conv-1"}, headers=ALICE
    )
    _assert_error(detail, 404, "SESSION_FILE_NOT_FOUND")

    delete = client.delete(
        f"{PREFIX}/sf_task_owned", params={"session_id": "conv-1"}, headers=ALICE
    )
    _assert_error(delete, 404, "SESSION_FILE_NOT_FOUND")

    listing = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)
    assert listing.json()["data"] == []
    task_scope = FileScope("alice", task_id="task-1")
    assert dao.get_by_file_id("sf_task_owned", task_scope) is not None


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------


def test_preview_returns_bounded_inspection_data(client):
    content = b"h1,h2\n1,2\n3,4\n"
    created = _upload(client, files=[_csv_file(content=content)]).json()["data"][0]

    response = client.get(
        f"{PREFIX}/{created['file_id']}/preview",
        params={"session_id": "conv-1"},
        headers=ALICE,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["file_id"] == created["file_id"]
    assert data["status"] == "ready"
    assert data["truncated"] is False
    assert data["error_code"] is None
    assert data["preview"]["rows"][0] == ["h1", "h2"]
    assert len(data["preview"]["rows"]) == 3
    assert "path" not in json.dumps(data)


def test_preview_failed_file_stays_visible_as_soft_warning(client):
    junk_pdf = ("files", ("data.pdf", b"not-a-real-pdf", "application/pdf"))
    created = _upload(client, files=[junk_pdf]).json()["data"][0]
    assert created["status"] == "preview_failed"
    assert created["error_code"] == "TYPE_MISMATCH"

    response = client.get(
        f"{PREFIX}/{created['file_id']}/preview",
        params={"session_id": "conv-1"},
        headers=ALICE,
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["status"] == "preview_failed"
    assert data["error_code"] == "TYPE_MISMATCH"
    assert data["preview"] == {}
    assert data["truncated"] is False


def test_preview_is_owner_and_scope_constrained(client):
    created = _upload(client).json()["data"][0]
    url = f"{PREFIX}/{created['file_id']}/preview"

    foreign = client.get(url, params={"session_id": "conv-1"}, headers=BOB)
    other_session = client.get(url, params={"session_id": "conv-2"}, headers=ALICE)
    for response in (foreign, other_session):
        _assert_error(response, 404, "SESSION_FILE_NOT_FOUND")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def test_download_streams_stored_bytes_as_attachment(client, transport):
    created = _upload(client).json()["data"][0]

    response = client.get(
        f"{PREFIX}/{created['file_id']}/download",
        params={"session_id": "conv-1"},
        headers=ALICE,
    )

    assert response.status_code == 200, response.text
    assert response.content == CSV_CONTENT
    assert response.headers["content-type"] == "application/octet-stream"
    disposition = response.headers["content-disposition"]
    assert "attachment" in disposition
    assert "report.csv" in disposition


def test_download_is_owner_and_scope_constrained(client):
    created = _upload(client).json()["data"][0]
    url = f"{PREFIX}/{created['file_id']}/download"

    foreign = client.get(url, params={"session_id": "conv-1"}, headers=BOB)
    other_session = client.get(url, params={"session_id": "conv-2"}, headers=ALICE)
    for response in (foreign, other_session):
        _assert_error(response, 404, "SESSION_FILE_NOT_FOUND")


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_requires_owner_and_removes_file(client):
    created = _upload(client).json()["data"][0]
    url = f"{PREFIX}/{created['file_id']}"

    foreign = client.delete(url, params={"session_id": "conv-1"}, headers=BOB)
    _assert_error(foreign, 404, "SESSION_FILE_NOT_FOUND")

    still_there = client.get(url, params={"session_id": "conv-1"}, headers=ALICE)
    assert still_there.status_code == 200

    deleted = client.delete(url, params={"session_id": "conv-1"}, headers=ALICE)
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True

    gone = client.get(url, params={"session_id": "conv-1"}, headers=ALICE)
    _assert_error(gone, 404, "SESSION_FILE_NOT_FOUND")


# ---------------------------------------------------------------------------
# Privacy and failure safety
# ---------------------------------------------------------------------------


def test_responses_never_expose_server_locations_or_hashes(client):
    content_sha256 = hashlib.sha256(CSV_CONTENT).hexdigest()
    upload_text = _upload(client).text
    created = json.loads(upload_text)["data"][0]

    bodies = [upload_text]
    for suffix in ("", f"/{created['file_id']}", f"/{created['file_id']}/preview"):
        response = client.get(
            f"{PREFIX}{suffix}", params={"session_id": "conv-1"}, headers=ALICE
        )
        assert response.status_code == 200, response.text
        bodies.append(response.text)
    capabilities = client.get(PREFIX + "/capabilities", headers=ALICE)
    bodies.append(capabilities.text)

    combined = "\n".join(bodies)
    for forbidden in ("file_path", "storage_uri", "sha256", "stub://"):
        assert forbidden not in combined
    assert content_sha256 not in combined


def test_service_unavailable_until_initialized():
    endpoints_module._reset_endpoints()
    app = FastAPI()
    app.include_router(endpoints_module.router, prefix=PREFIX)
    client = TestClient(app)

    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)

    _assert_error(response, 503, "SESSION_FILE_SERVICE_UNAVAILABLE")


# ---------------------------------------------------------------------------
# Transport validation aligned with persistence/materialization
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_session",
    ["has/slash", "has\\backslash", "nul\x00byte", ".", ".."],
)
def test_session_id_rejects_unsafe_or_reserved_values(client, bad_session):
    response = client.post(
        PREFIX,
        data={"session_id": bad_session},
        files=[_csv_file()],
        headers=ALICE,
    )

    _assert_error(response, 400, "INVALID_SESSION_ID")


def test_session_id_rejects_overlong_id(client):
    response = client.post(
        PREFIX,
        data={"session_id": "s" * 129},
        files=[_csv_file()],
        headers=ALICE,
    )

    _assert_error(response, 400, "INVALID_SESSION_ID")


def test_session_id_boundary_128_bytes_is_accepted(client):
    response = client.post(
        PREFIX,
        data={"session_id": "s" * 128},
        files=[_csv_file()],
        headers=ALICE,
    )

    assert response.status_code == 200, response.text


def test_session_id_dot_substrings_are_allowed(client):
    # Only the exact values "." and ".." are rejected (materializer parity);
    # dots inside a normal id stay valid.
    response = client.post(
        PREFIX,
        data={"session_id": "conv..1.draft"},
        files=[_csv_file()],
        headers=ALICE,
    )

    assert response.status_code == 200, response.text


# ---------------------------------------------------------------------------
# Stable mapping of registry error codes
# ---------------------------------------------------------------------------


class _RegistryErrorService:
    """Service double failing with one deterministic registry code."""

    def __init__(self, code: str):
        self._code = code

    def list_files(self, *, owner_id, session_id):
        from dbgpt_serve.session_file.registry import SessionFileRegistryError

        raise SessionFileRegistryError(self._code, "simulated registry failure")


def _client_with_service(service) -> TestClient:
    config = ServeConfig(
        max_files_per_upload=2,
        max_file_bytes=64,
        max_upload_bytes=96,
        max_owner_bytes=512,
        upload_concurrency_advice=3,
        upload_chunk_bytes=8,
        upload_spool_bytes=32,
        download_chunk_bytes=8,
        max_file_name_bytes=32,
    )
    app = FastAPI()
    app.include_router(endpoints_module.router, prefix=PREFIX)
    endpoints_module.init_endpoints(MagicMock(), service, config)
    return TestClient(app)


@pytest.mark.parametrize(
    "registry_code,expected_status,expected_err_code",
    [
        ("FILE_TOO_LARGE", 413, "FILE_TOO_LARGE"),
        ("BATCH_TOO_LARGE", 413, "BATCH_TOO_LARGE"),
        ("TOO_MANY_FILES", 400, "TOO_MANY_FILES"),
        ("SIZE_MISMATCH", 400, "SIZE_MISMATCH"),
        ("QUOTA_EXCEEDED", 409, "QUOTA_EXCEEDED"),
        ("QUOTA_LOCK_TIMEOUT", 503, "QUOTA_LOCK_TIMEOUT"),
        ("MATERIALIZE_FAILED", 500, "MATERIALIZE_FAILED"),
        ("FINALIZE_FAILED", 500, "FINALIZE_FAILED"),
        ("INVALID_SCOPE_COMPONENT", 400, "INVALID_SCOPE_COMPONENT"),
    ],
)
def test_registry_error_codes_map_to_stable_http(
    registry_code, expected_status, expected_err_code
):
    client = _client_with_service(_RegistryErrorService(registry_code))

    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)

    _assert_error(response, expected_status, expected_err_code)


def test_unknown_registry_error_stays_generic_internal():
    client = _client_with_service(_RegistryErrorService("SOME_FUTURE_CODE"))

    response = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)

    _assert_error(response, 500, "SESSION_FILE_INTERNAL")


# ---------------------------------------------------------------------------
# Batch upload compensation
# ---------------------------------------------------------------------------


def test_failed_batch_rolls_back_files_ingested_earlier_in_request(client, transport):
    from dbgpt_serve.session_file.registry import SessionFileRegistryError

    _, service = transport
    original_ingest = service.ingest
    original_delete = service.delete_file
    calls = {"ingest": 0}
    deleted_ids: List[str] = []

    def _fail_second(*args, **kwargs):
        calls["ingest"] += 1
        if calls["ingest"] == 2:
            raise SessionFileRegistryError("QUOTA_EXCEEDED", "simulated quota failure")
        return original_ingest(*args, **kwargs)

    def _delete_spy(*args, **kwargs):
        deleted_ids.append(kwargs["file_id"])
        return original_delete(*args, **kwargs)

    service.ingest = _fail_second
    service.delete_file = _delete_spy

    files = [_csv_file("first.csv"), _csv_file("second.csv")]
    response = _upload(client, files=files)

    _assert_error(response, 409, "QUOTA_EXCEEDED")
    assert deleted_ids == ["sf_test_0001"]
    listing = client.get(PREFIX, params={"session_id": "conv-1"}, headers=ALICE)
    assert listing.json()["data"] == []

    # A retry of the same upload starts clean: the failed request left no
    # residue, so the retried file keeps ordinal 0.
    retry = _upload(client, files=[_csv_file("first.csv")])
    assert retry.status_code == 200, retry.text
    (item,) = retry.json()["data"]
    assert item["ordinal"] == 0


# ---------------------------------------------------------------------------
# Event loop safety: blocking registry work must run off the loop
# ---------------------------------------------------------------------------


def test_ingest_runs_off_the_event_loop(client, transport):
    """Sync registry work must never run on (and join) the event loop."""
    import asyncio

    _, service = transport
    original_ingest = service.ingest
    probe: Dict[str, bool] = {}

    def _probed_ingest(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            probe["off_loop"] = True
        else:
            probe["off_loop"] = False
        return original_ingest(*args, **kwargs)

    service.ingest = _probed_ingest

    response = _upload(client)

    assert response.status_code == 200, response.text
    assert probe == {"off_loop": True}
