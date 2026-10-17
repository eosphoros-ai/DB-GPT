import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from dbgpt_serve.utils.auth import UserRequest


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self.content_type = "text/x-python"
        self._buffer = io.BytesIO(content)
        self.read_calls = []
        self.read_sizes = self.read_calls

    async def read(self, size: int = -1) -> bytes:
        self.read_calls.append(size)
        return self._buffer.read(size)


@pytest.mark.asyncio
async def test_python_file_upload_rejects_traversal_filename(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("../../outside.py", b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (tmp_path / "outside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_absolute_filename(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile(str(tmp_path / "outside.py"), b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (tmp_path / "outside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_allows_plain_filename_inside_user_dir(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b"print('inside')"),
        UserRequest(user_id="alice"),
    )

    expected_path = tmp_path / "python_uploads" / "alice" / "inside.py"
    assert result.success is True
    assert result.data == str(expected_path)
    assert expected_path.read_bytes() == b"print('inside')"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlink_escape(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    outside_dir = tmp_path / "outside"
    upload_dir.mkdir(parents=True)
    outside_dir.mkdir()
    try:
        (upload_dir / "linked").symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("linked/escaped.py", b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (outside_dir / "escaped.py").exists()


@pytest.mark.parametrize(
    "filename",
    ["..\\..\\evil.py", "sub\\nested.py", "..\\evil.py"],
)
@pytest.mark.asyncio
async def test_python_file_upload_rejects_windows_separators(
    tmp_path, monkeypatch, filename
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile(filename, b"print('escaped')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    owner_root = tmp_path / "python_uploads" / "alice"
    leftovers = list(owner_root.rglob("*")) if owner_root.exists() else []
    assert not any(path.is_file() for path in leftovers)


@pytest.mark.asyncio
async def test_python_file_upload_rejects_traversal_user_id(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    outside_dir = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_dir.mkdir()

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('inside')"),
            UserRequest(user_id=f"../../{outside_dir.name}"),
        )

    assert exc_info.value.status_code == 400
    assert not (outside_dir / "inside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_whitespace_user_id(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('inside')"),
            UserRequest(user_id=" alice "),
        )

    assert exc_info.value.status_code == 400
    assert not (tmp_path / "python_uploads" / " alice ").exists()


@pytest.mark.parametrize("user_id", [None, "", "   "])
@pytest.mark.asyncio
async def test_python_file_upload_defaults_empty_user_id(
    tmp_path, monkeypatch, user_id
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b"print('inside')"),
        UserRequest(user_id=user_id),
    )

    expected_path = tmp_path / "python_uploads" / "default" / "inside.py"
    assert result.success is True
    assert result.data == str(expected_path)
    assert expected_path.read_bytes() == b"print('inside')"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_other_owner_traversal(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("../bob/secret.py", b"print('cross-owner')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (tmp_path / "python_uploads" / "bob").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlinked_owner_root(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    uploads_root = tmp_path / "python_uploads"
    uploads_root.mkdir(parents=True)
    escape_dir = tmp_path / "escape"
    escape_dir.mkdir()
    try:
        (uploads_root / "mallory").symlink_to(escape_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('escaped')"),
            UserRequest(user_id="mallory"),
        )

    assert exc_info.value.status_code == 400
    assert not (escape_dir / "inside.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_rejects_traversing_owner_id(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('escaped')"),
            UserRequest(user_id="../evil"),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_python_file_upload_never_overwrites_via_symlink(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    upload_dir.mkdir(parents=True)
    target = upload_dir / "target.py"
    target.write_bytes(b"original")
    try:
        (upload_dir / "link.py").symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("link.py", b"print('overwritten')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert target.read_bytes() == b"original"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlinked_parent_component(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    real_dir = upload_dir / "real"
    real_dir.mkdir(parents=True)
    try:
        (upload_dir / "linkdir").symlink_to(real_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("linkdir/renamed.py", b"print('renamed target')"),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert not (real_dir / "renamed.py").exists()


@pytest.mark.asyncio
async def test_python_file_upload_reads_and_writes_in_bounded_chunks(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    payload = (b"chunked-payload " * 12000) + b"tail"
    upload = FakeUploadFile("script.py", payload)

    result = await python_upload_api.python_file_upload(
        upload,
        UserRequest(user_id="alice"),
    )

    expected_path = tmp_path / "python_uploads" / "alice" / "script.py"
    assert result.success is True
    assert expected_path.read_bytes() == payload
    assert upload.read_calls, "upload must be read at least once"
    assert all(0 < size for size in upload.read_calls[:-1])
    assert max(upload.read_calls[:-1]) <= python_upload_api._UPLOAD_CHUNK_BYTES


@pytest.mark.asyncio
async def test_python_file_upload_overwrites_existing_regular_file(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    upload_dir.mkdir(parents=True)
    existing = upload_dir / "inside.py"
    existing.write_bytes(b"old content")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b"new content"),
        UserRequest(user_id="alice"),
    )

    assert result.success is True
    assert result.data == str(existing)
    assert existing.read_bytes() == b"new content"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_empty_file_without_touching_disk(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    upload_dir = tmp_path / "python_uploads" / "alice"
    upload_dir.mkdir(parents=True)
    existing = upload_dir / "inside.py"
    existing.write_bytes(b"old content")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_file_upload(
        FakeUploadFile("inside.py", b""),
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert existing.read_bytes() == b"old content"


@pytest.mark.asyncio
async def test_python_file_upload_rejects_symlinked_upload_root(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    base_dir = tmp_path / "work"
    base_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    uploads_root = base_dir / "python_uploads"
    try:
        uploads_root.symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are not available in this environment: {exc}")

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(base_dir))
    )

    with pytest.raises(HTTPException) as exc_info:
        await python_upload_api.python_file_upload(
            FakeUploadFile("inside.py", b"print('inside')"),
            UserRequest(user_id="alice"),
        )

    assert exc_info.value.status_code == 400
    assert not (outside_dir / "alice" / "inside.py").exists()


@pytest.mark.asyncio
async def test_python_files_upload_keeps_batch_together(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )
    registrations = []
    registered_datasets = []
    monkeypatch.setattr(
        python_upload_api,
        "_register_uploaded_dataset",
        lambda database_name, database_path, user_id: registrations.append(
            (database_name, database_path, user_id)
        ),
    )

    class FakeDataset:
        def __init__(self, values):
            self._values = values

        def public_dict(self):
            return {
                "dataset_id": self._values["dataset_id"],
                "conversation_id": self._values["conversation_id"],
                "database_name": self._values["database_name"],
                "database_type": "sqlite",
                "files": [
                    {key: value for key, value in item.items() if key != "stored_path"}
                    for item in self._values["files"]
                ],
                "tables": [
                    table for item in self._values["files"] for table in item["tables"]
                ],
                "relationship_candidates": self._values["relationships"],
            }

    class FakeDatasetService:
        def register_ready(self, **values):
            registered_datasets.append(values)
            return FakeDataset(values)

        def delete_registry_record(self, dataset_id, owner_id):
            return True

    monkeypatch.setattr(
        python_upload_api,
        "_get_uploaded_dataset_service",
        lambda: FakeDatasetService(),
    )

    result = await python_upload_api.python_files_upload(
        [
            FakeUploadFile("orders.csv", b"order_id,customer_id\n1,10\n"),
            FakeUploadFile("customers.csv", b"customer_id,city\n10,Hangzhou\n"),
        ],
        "conversation-1",
        UserRequest(user_id="alice"),
    )

    assert result.success is True
    paths = [Path(item["stored_path"]) for item in registered_datasets[0]["files"]]
    assert [path.name for path in paths] == ["orders.csv", "customers.csv"]
    assert paths[0].parent == paths[1].parent
    assert paths[0].parent.name.startswith("batch-")
    assert paths[0].read_bytes() == b"order_id,customer_id\n1,10\n"
    assert paths[1].read_bytes() == b"customer_id,city\n10,Hangzhou\n"
    assert result.data["database_type"] == "sqlite"
    assert registered_datasets[0]["database_path"].is_file()
    assert [item["table_name"] for item in result.data["tables"]] == [
        "orders",
        "customers",
    ]
    assert result.data["relationship_candidates"] == [
        {
            "column": "customer_id",
            "left_table": "orders",
            "right_table": "customers",
            "sample_distinct_overlap": 1,
            "status": "candidate_only",
        }
    ]
    assert len(registrations) == 1
    assert registrations[0][0] == result.data["database_name"]
    assert registrations[0][1] == registered_datasets[0]["database_path"]
    assert registrations[0][2] == "alice"
    assert result.data["conversation_id"] == "conversation-1"
    assert "file_paths" not in result.data
    assert "database_path" not in result.data
    assert all("stored_path" not in item for item in result.data["files"])


@pytest.mark.asyncio
async def test_python_files_upload_rejects_duplicate_names(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_files_upload(
        [
            FakeUploadFile("orders.csv", b"first"),
            FakeUploadFile("ORDERS.CSV", b"second"),
        ],
        "conversation-1",
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert "Duplicate filename" in result.err_msg
    user_dir = tmp_path / "python_uploads" / "alice"
    assert not user_dir.exists() or list(user_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_python_files_upload_enforces_count_file_and_batch_limits(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )
    monkeypatch.setattr(python_upload_api, "_MAX_BATCH_FILES", 1)
    too_many = await python_upload_api.python_files_upload(
        [FakeUploadFile("a.csv", b"a\n1\n"), FakeUploadFile("b.csv", b"b\n1\n")],
        "conversation-1",
        UserRequest(user_id="alice"),
    )
    assert too_many.success is False
    assert "maximum 1" in too_many.err_msg

    monkeypatch.setattr(python_upload_api, "_MAX_BATCH_FILES", 16)
    monkeypatch.setattr(python_upload_api, "_MAX_FILE_BYTES", 4)
    oversized_file = FakeUploadFile("a.csv", b"12345")
    too_large = await python_upload_api.python_files_upload(
        [oversized_file],
        "conversation-1",
        UserRequest(user_id="alice"),
    )
    assert too_large.success is False
    assert "File exceeds" in too_large.err_msg
    assert oversized_file.read_sizes == [5]

    monkeypatch.setattr(python_upload_api, "_MAX_FILE_BYTES", 10)
    monkeypatch.setattr(python_upload_api, "_MAX_BATCH_BYTES", 6)
    batch_too_large = await python_upload_api.python_files_upload(
        [FakeUploadFile("a.csv", b"1234"), FakeUploadFile("b.csv", b"5678")],
        "conversation-1",
        UserRequest(user_id="alice"),
    )
    assert batch_too_large.success is False
    assert "Batch exceeds" in batch_too_large.err_msg


@pytest.mark.asyncio
async def test_python_files_upload_rejects_unsupported_type_and_missing_conversation(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )
    unsupported = await python_upload_api.python_files_upload(
        [FakeUploadFile("report.pdf", b"not-a-table")],
        "conversation-1",
        UserRequest(user_id="alice"),
    )
    assert unsupported.success is False
    assert "Unsupported tabular file type" in unsupported.err_msg

    missing_conversation = await python_upload_api.python_files_upload(
        [FakeUploadFile("orders.csv", b"order_id\n1\n")],
        "",
        UserRequest(user_id="alice"),
    )
    assert missing_conversation.success is False
    assert "conversation id" in missing_conversation.err_msg


@pytest.mark.asyncio
async def test_python_files_upload_rejects_path_filename(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_files_upload(
        [FakeUploadFile("../orders.csv", b"order_id\n1\n")],
        "conversation-1",
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert "path separators" in result.err_msg
    assert not (tmp_path / "orders.csv").exists()


@pytest.mark.asyncio
async def test_python_files_upload_rolls_back_partial_batch(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    result = await python_upload_api.python_files_upload(
        [
            FakeUploadFile("orders.csv", b"order_id\n1\n"),
            FakeUploadFile("customers.csv", b""),
        ],
        "conversation-1",
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    user_dir = tmp_path / "python_uploads" / "alice"
    assert user_dir.exists()
    assert list(user_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_python_files_upload_rolls_back_when_registration_fails(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )

    def fail_registration(database_name, database_path, user_id):
        raise RuntimeError("metadata storage unavailable")

    monkeypatch.setattr(
        python_upload_api, "_register_uploaded_dataset", fail_registration
    )

    result = await python_upload_api.python_files_upload(
        [FakeUploadFile("orders.csv", b"order_id\n1\n")],
        "conversation-1",
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert "metadata storage unavailable" in result.err_msg
    user_dir = tmp_path / "python_uploads" / "alice"
    assert user_dir.exists()
    assert list(user_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_python_files_upload_rolls_back_datasource_when_registry_fails(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api

    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )
    registered = []
    unregistered = []
    monkeypatch.setattr(
        python_upload_api,
        "_register_uploaded_dataset",
        lambda database_name, database_path, user_id: registered.append(database_name),
    )
    monkeypatch.setattr(
        python_upload_api,
        "_unregister_uploaded_dataset",
        lambda database_name: unregistered.append(database_name),
    )

    class FailingRegistry:
        def register_ready(self, **values):
            raise RuntimeError("registry unavailable")

    monkeypatch.setattr(
        python_upload_api,
        "_get_uploaded_dataset_service",
        lambda: FailingRegistry(),
    )

    result = await python_upload_api.python_files_upload(
        [FakeUploadFile("orders.csv", b"order_id\n1\n")],
        "conversation-1",
        UserRequest(user_id="alice"),
    )

    assert result.success is False
    assert "registry unavailable" in result.err_msg
    assert unregistered == registered
    user_dir = tmp_path / "python_uploads" / "alice"
    assert user_dir.exists()
    assert list(user_dir.iterdir()) == []


def test_register_uploaded_dataset_rolls_back_metadata_after_cache_failure(
    tmp_path, monkeypatch
):
    from dbgpt_app.openapi.api_v1 import python_upload_api
    from dbgpt_serve.datasource.manages import ConnectorManager

    class FakeStorage:
        def __init__(self):
            self.records = {}
            self.deleted = []

        def get_by_names(self, database_name):
            return self.records.get(database_name)

        def add_file_db(
            self, database_name, database_type, database_path, comment, user_id
        ):
            self.records[database_name] = {
                "db_type": database_type,
                "file_path": database_path,
                "comment": comment,
                "user_id": user_id,
            }

        def delete_db(self, database_name):
            self.deleted.append(database_name)
            self.records.pop(database_name, None)

    class FakeManager:
        def __init__(self):
            self.storage = FakeStorage()
            self.invalidations = 0

        def invalidate_connector(self, database_name):
            self.invalidations += 1
            if self.invalidations == 1:
                raise RuntimeError("cache unavailable")

    manager = FakeManager()
    monkeypatch.setattr(
        python_upload_api.CFG, "SYSTEM_APP", SimpleNamespace(work_dir=str(tmp_path))
    )
    monkeypatch.setattr(ConnectorManager, "get_instance", lambda system_app: manager)

    with pytest.raises(RuntimeError, match="cache unavailable"):
        python_upload_api._register_uploaded_dataset(
            "upload_alice_123", tmp_path / "dataset.sqlite", "alice"
        )

    assert manager.storage.records == {}
    assert manager.storage.deleted == ["upload_alice_123"]
    assert manager.invalidations == 2
