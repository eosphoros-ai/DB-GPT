"""History payload v2 ``input_files`` snapshots for ReAct chat turns.

Covers:
- success and error history payloads both carry ``version: 2`` and a
  current-turn ``input_files`` snapshot from the shared adapter builder;
- snapshots contain only public metadata (file_id/name/size/media_type/
  kind/status/ordinal) — never paths, storage URIs, owner ids, hashes or
  inspection bodies;
- pure-text turns persist an empty snapshot; each payload only snapshots
  its own turn (later turns resolve files fresh from the registry);
- legacy v1 payloads remain readable (the share scrubber leaves them
  untouched).
"""

import importlib
import io
import json

import pytest
from sqlalchemy.pool import StaticPool

from dbgpt.storage.metadata import db
from dbgpt_serve.session_file.inspector import SessionFileInspector
from dbgpt_serve.session_file.models.dao import SessionFileDao
from dbgpt_serve.session_file.models.models import SessionFileEntity  # noqa: F401
from dbgpt_serve.session_file.registry import SessionFileRegistry

OWNER = "alice"
SESSION = "sess-1"
CSV_CONTENT = b"colA,colB\n1,2\n"
TXT_CONTENT = b"hello history"

_SNAPSHOT_KEYS = {
    "file_id",
    "name",
    "size",
    "media_type",
    "kind",
    "status",
    "ordinal",
}

_PRIVATE_MARKERS = (
    "storage_uri",
    "file_path",
    "work_root",
    "python_uploads",
    "owner_id",
    "sha256",
    "inspection",
)


class _FakeStorageClient:
    """In-memory FileStorageClient seam double."""

    def __init__(self):
        self.saved = {}

    def save_file(
        self,
        bucket,
        file_name,
        file_data,
        storage_type=None,
        custom_metadata=None,
        file_id=None,
    ):
        data = file_data.read()
        uri = f"dbgpt-fs://local/{bucket}/{file_id}"
        self.saved[uri] = data
        return uri

    def get_file(self, uri):
        if uri not in self.saved:
            raise FileNotFoundError(uri)
        from types import SimpleNamespace

        metadata = SimpleNamespace(
            file_id=uri.rsplit("/", 1)[-1],
            file_size=len(self.saved[uri]),
            file_hash="-1",
            uri=uri,
        )
        return io.BytesIO(self.saved[uri]), metadata

    def delete_file(self, uri):
        return self.saved.pop(uri, None) is not None


def _trusted_inspector() -> SessionFileInspector:
    base = SessionFileInspector()
    return SessionFileInspector(
        optional_import=importlib.import_module,
        parsers={
            ".csv": base._parse_delimited,
            ".txt": base._parse_text,
        },
    )


@pytest.fixture()
def registry(tmp_path):
    db.init_db(
        "sqlite:///:memory:",
        engine_args={
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        },
    )
    db.create_all()
    from dbgpt_serve.session_file.config import ServeConfig

    return SessionFileRegistry(
        storage_client=_FakeStorageClient(),
        dao=SessionFileDao(),
        inspector=_trusted_inspector(),
        config=ServeConfig(),
        work_root=tmp_path / "work",
    )


def _ingest(
    registry,
    name="report.csv",
    content=CSV_CONTENT,
    media="text/csv",
    owner=OWNER,
    session=SESSION,
):
    return registry.ingest(
        owner_id=owner,
        session_id=session,
        display_name=name,
        media_type=media,
        stream=io.BytesIO(content),
        size_bytes=len(content),
    )


def _open_manifests(registry, *file_ids):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        open_session_attachments,
    )

    ctx = open_session_attachments(
        registry,
        owner_id=OWNER,
        session_id=SESSION,
        file_ids=tuple(file_ids),
    )
    try:
        return list(ctx.manifests)
    finally:
        ctx.close()


def test_input_files_v2_snapshot_contains_only_public_fields(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    record = _ingest(registry)
    manifests = _open_manifests(registry, record.file_id)

    snapshot = build_input_files_v2(manifests)

    assert len(snapshot) == 1
    entry = snapshot[0]
    assert set(entry) == _SNAPSHOT_KEYS
    assert entry["file_id"] == record.file_id
    assert entry["name"] == "report.csv"
    assert entry["size"] == len(CSV_CONTENT)
    assert entry["media_type"] == "text/csv"
    assert entry["kind"] == "table"
    assert entry["status"] == "ready"
    assert entry["ordinal"] == 0


def test_input_files_v2_snapshot_serializes_without_private_markers(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    record = _ingest(registry)
    manifests = _open_manifests(registry, record.file_id)

    serialized = json.dumps(build_input_files_v2(manifests), ensure_ascii=False)

    assert record.storage_uri not in serialized
    assert record.sha256 not in serialized
    assert str(registry.work_root) not in serialized
    assert OWNER not in serialized.replace("report.csv", "")
    for marker in _PRIVATE_MARKERS:
        assert marker not in serialized


def test_success_history_payload_v2_includes_current_turn_snapshot(registry):
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    record = _ingest(registry)
    manifests = _open_manifests(registry, record.file_id)

    payload = json.loads(
        _build_react_history_payload(
            final_content="done",
            steps=[{"id": "s1", "status": "done"}],
            task_plan=[],
            generated_images=[],
            sub_agents=[],
            input_files=build_input_files_v2(manifests),
        )
    )

    assert payload["version"] == 2
    assert payload["type"] == "react-agent"
    assert payload["final_content"] == "done"
    assert payload["input_files"] == build_input_files_v2(manifests)
    entry = payload["input_files"][0]
    assert set(entry) == _SNAPSHOT_KEYS
    assert entry["file_id"] == record.file_id


def test_error_history_payload_v2_includes_same_snapshot_shape(registry):
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    record = _ingest(registry)
    manifests = _open_manifests(registry, record.file_id)

    payload = json.loads(
        _build_react_history_payload(
            final_content="React agent failed: boom",
            steps=[{"id": "s1", "status": "failed"}],
            task_plan=[],
            generated_images=[],
            sub_agents=[],
            input_files=build_input_files_v2(manifests),
        )
    )

    assert payload["version"] == 2
    assert payload["input_files"] == build_input_files_v2(manifests)
    serialized = json.dumps(payload, ensure_ascii=False)
    for marker in _PRIVATE_MARKERS:
        assert marker not in serialized


def test_history_payload_v2_text_only_turn_persists_empty_snapshot():
    from dbgpt_app.openapi.api_v1.agentic_data_api import (
        _build_react_history_payload,
    )
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    payload = json.loads(
        _build_react_history_payload(
            final_content="plain answer",
            steps=[],
            task_plan=[],
            generated_images=[],
            sub_agents=[],
            input_files=build_input_files_v2([]),
        )
    )

    assert payload["version"] == 2
    assert payload["input_files"] == []


def test_history_payload_snapshots_only_the_current_turn(registry):
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        build_input_files_v2,
    )

    first = _ingest(registry, name="a.csv")
    second = _ingest(registry, name="b.csv", content=b"x,y\n3,4\n")

    turn_one = build_input_files_v2(_open_manifests(registry, first.file_id))
    turn_two = build_input_files_v2(_open_manifests(registry, second.file_id))

    assert [entry["file_id"] for entry in turn_one] == [first.file_id]
    assert [entry["file_id"] for entry in turn_two] == [second.file_id]


def test_legacy_v1_payload_remains_readable_and_untouched_by_share_scrub():
    from dbgpt_app.openapi.api_v1.attachment_react_adapter import (
        REACT_HISTORY_PAYLOAD_VERSION,
        scrub_react_history_for_share,
    )

    assert REACT_HISTORY_PAYLOAD_VERSION == 2
    legacy = json.dumps(
        {
            "version": 1,
            "type": "react-agent",
            "final_content": "legacy answer",
            "steps": [{"id": "s1", "status": "done"}],
            "task_plan": [],
            "generated_images": [],
            "sub_agents": [],
        },
        ensure_ascii=False,
    )

    scrubbed = scrub_react_history_for_share(legacy)

    assert scrubbed == legacy
    parsed = json.loads(scrubbed)
    assert parsed["version"] == 1
    assert parsed["final_content"] == "legacy answer"
    assert parsed["steps"][0]["id"] == "s1"
