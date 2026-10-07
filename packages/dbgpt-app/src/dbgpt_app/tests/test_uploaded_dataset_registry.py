from pathlib import Path

import pytest

from dbgpt_app.openapi.api_v1.uploaded_dataset_registry import (
    UploadedDatasetAccessError,
    UploadedDatasetEntity,
    UploadedDatasetNotFoundError,
    UploadedDatasetService,
    validate_legacy_user_paths,
)


class MemoryDatasetDao:
    def __init__(self):
        self.rows = {}

    def create_dataset(self, values):
        self.rows[values["dataset_id"]] = UploadedDatasetEntity(**values)

    def get_owned(self, dataset_id, owner_id):
        row = self.rows.get(dataset_id)
        return row if row is not None and row.owner_id == owner_id else None

    def get_latest_for_conversation(self, owner_id, conversation_id):
        matches = [
            row
            for row in self.rows.values()
            if row.owner_id == owner_id
            and row.conversation_id == conversation_id
            and row.status == "ready"
        ]
        return matches[-1] if matches else None

    def delete_dataset(self, dataset_id, owner_id):
        if self.get_owned(dataset_id, owner_id) is None:
            return False
        del self.rows[dataset_id]
        return True


def _register_dataset(tmp_path: Path):
    batch_dir = tmp_path / "python_uploads" / "alice" / "batch-123"
    batch_dir.mkdir(parents=True)
    csv_path = batch_dir / "orders.csv"
    csv_path.write_text("order_id,total\n1,12.5\n2,8.0\n", encoding="utf-8")
    database_path = batch_dir / "dataset.sqlite"
    database_path.touch()
    service = UploadedDatasetService(dao=MemoryDatasetDao())
    dataset = service.register_ready(
        dataset_id="dataset-1",
        owner_id="alice",
        conversation_id="conversation-1",
        database_name="upload_alice_dataset1",
        database_path=database_path,
        batch_dir=batch_dir,
        files=[
            {
                "file_id": "file-orders",
                "name": "orders.csv",
                "stored_path": str(csv_path),
                "size_bytes": csv_path.stat().st_size,
                "content_type": "text/csv",
                "tables": [
                    {
                        "source_file": "orders.csv",
                        "source_sheet": None,
                        "table_name": "orders",
                        "row_count": 2,
                        "columns": ["order_id", "total"],
                    }
                ],
            }
        ],
        relationships=[],
    )
    return service, dataset


def test_registry_returns_only_public_metadata_and_bounded_preview(tmp_path):
    service, dataset = _register_dataset(tmp_path)

    public = dataset.public_dict()
    assert public["dataset_id"] == "dataset-1"
    assert "database_path" not in public
    assert "stored_path" not in public["files"][0]

    preview = service.preview_file(
        "dataset-1",
        "file-orders",
        "alice",
        "conversation-1",
        row_limit=1,
    )
    assert preview["columns"] == ["order_id", "total"]
    assert preview["rows"] == [{"order_id": 1, "total": 12.5}]
    assert preview["shape"] == [2, 2]
    assert preview["truncated"] is True


def test_registry_hides_dataset_from_other_users_and_conversations(tmp_path):
    service, _ = _register_dataset(tmp_path)

    with pytest.raises(UploadedDatasetNotFoundError):
        service.resolve_owned("dataset-1", "bob", "conversation-1")
    with pytest.raises(UploadedDatasetNotFoundError):
        service.resolve_owned("dataset-1", "alice", "conversation-2")


def test_registry_allows_only_an_owned_bound_replay_task(tmp_path, monkeypatch):
    service, _ = _register_dataset(tmp_path)
    monkeypatch.setattr(
        service,
        "_task_authorizes_dataset",
        lambda task_id, owner_id, dataset_id: (
            (
                task_id,
                owner_id,
                dataset_id,
            )
            == ("task-1", "alice", "dataset-1")
        ),
    )

    resolved = service.resolve_owned(
        "dataset-1",
        "alice",
        "fresh-run-conversation",
        replay_task_id="task-1",
    )
    assert resolved.database_name == "upload_alice_dataset1"
    with pytest.raises(UploadedDatasetNotFoundError):
        service.resolve_owned(
            "dataset-1",
            "alice",
            "fresh-run-conversation",
            replay_task_id="task-other",
        )


def test_registry_rejects_manifest_paths_moved_outside_batch(tmp_path):
    service, dataset = _register_dataset(tmp_path)
    row = service._dao.rows[dataset.dataset_id]
    row.manifest_json = row.manifest_json.replace("orders.csv", "../../outside.csv")

    with pytest.raises((UploadedDatasetAccessError, UploadedDatasetNotFoundError)):
        service.resolve_owned("dataset-1", "alice", "conversation-1")


def test_legacy_paths_cannot_cross_user_upload_roots(tmp_path, monkeypatch):
    from dbgpt_app.openapi.api_v1 import uploaded_dataset_registry

    alice_root = tmp_path / "python_uploads" / "alice"
    bob_root = tmp_path / "python_uploads" / "bob"
    alice_root.mkdir(parents=True)
    bob_root.mkdir(parents=True)
    alice_file = alice_root / "owned.csv"
    bob_file = bob_root / "private.csv"
    alice_file.write_text("id\n1\n", encoding="utf-8")
    bob_file.write_text("id\n2\n", encoding="utf-8")
    monkeypatch.setattr(uploaded_dataset_registry, "upload_work_dir", lambda: tmp_path)

    assert validate_legacy_user_paths([str(alice_file)], "alice") == [
        str(alice_file.resolve())
    ]
    with pytest.raises(UploadedDatasetAccessError):
        validate_legacy_user_paths([str(bob_file)], "alice")
