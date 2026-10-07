"""Durable ownership and preview boundary for uploaded tabular datasets.

The browser receives opaque dataset/file identifiers only.  Absolute paths and
the generated SQLite path stay in this server-side registry so callers cannot
substitute another user's files through ``ext_info`` or the preview API.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT

from dbgpt._private.config import Config
from dbgpt.storage.metadata import BaseDao, Model


def _json_text_type():
    return Text().with_variant(LONGTEXT(), "mysql")


class UploadedDatasetEntity(Model):
    """One atomically registered upload group owned by one authenticated user."""

    __tablename__ = "dbgpt_uploaded_dataset"

    dataset_id = Column(String(64), primary_key=True)
    owner_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(String(255), nullable=False, index=True)
    database_name = Column(String(255), nullable=False, unique=True, index=True)
    database_path = Column(Text, nullable=False)
    batch_dir = Column(Text, nullable=False)
    manifest_json = Column(_json_text_type(), nullable=False)
    relationships_json = Column(_json_text_type(), nullable=False, default="[]")
    status = Column(String(32), nullable=False, default="ready", index=True)
    error_message = Column(Text, nullable=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class UploadedDatasetNotFoundError(LookupError):
    """Raised for missing and non-owned datasets without revealing which."""


class UploadedDatasetAccessError(PermissionError):
    """Raised when a dataset is used outside its bound execution context."""


@dataclass(frozen=True)
class AuthorizedUploadedDataset:
    dataset_id: str
    owner_id: str
    conversation_id: str
    database_name: str
    database_path: Path
    batch_dir: Path
    files: Tuple[Dict[str, Any], ...]
    relationships: Tuple[Dict[str, Any], ...]

    @property
    def file_paths(self) -> List[str]:
        return [str(item["stored_path"]) for item in self.files]

    def public_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "conversation_id": self.conversation_id,
            "database_name": self.database_name,
            "database_type": "sqlite",
            "files": [_public_file(item) for item in self.files],
            "tables": [
                table
                for item in self.files
                for table in item.get("tables", [])
                if isinstance(table, dict)
            ],
            "relationship_candidates": list(self.relationships),
        }


def _public_file(item: Dict[str, Any]) -> Dict[str, Any]:
    """Return client-safe metadata, deliberately excluding ``stored_path``."""

    return {
        "file_id": item.get("file_id"),
        "name": item.get("name"),
        "size_bytes": int(item.get("size_bytes") or 0),
        "content_type": item.get("content_type") or "application/octet-stream",
        "tables": [
            table for table in item.get("tables", []) if isinstance(table, dict)
        ],
    }


class UploadedDatasetDao(BaseDao):
    """Small DAO kept local to the upload feature for an explicit trust boundary."""

    def create_dataset(self, values: Dict[str, Any]) -> None:
        with self.session() as session:
            session.add(UploadedDatasetEntity(**values))

    def get_owned(
        self, dataset_id: str, owner_id: str
    ) -> Optional[UploadedDatasetEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(UploadedDatasetEntity)
                .filter(
                    UploadedDatasetEntity.dataset_id == dataset_id,
                    UploadedDatasetEntity.owner_id == owner_id,
                )
                .first()
            )
            return self._detach(row)

    def get_latest_for_conversation(
        self, owner_id: str, conversation_id: str
    ) -> Optional[UploadedDatasetEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(UploadedDatasetEntity)
                .filter(
                    UploadedDatasetEntity.owner_id == owner_id,
                    UploadedDatasetEntity.conversation_id == conversation_id,
                    UploadedDatasetEntity.status == "ready",
                )
                .order_by(UploadedDatasetEntity.gmt_created.desc())
                .first()
            )
            return self._detach(row)

    def delete_dataset(self, dataset_id: str, owner_id: str) -> bool:
        with self.session() as session:
            count = (
                session.query(UploadedDatasetEntity)
                .filter(
                    UploadedDatasetEntity.dataset_id == dataset_id,
                    UploadedDatasetEntity.owner_id == owner_id,
                )
                .delete()
            )
            return bool(count)

    @staticmethod
    def _detach(
        row: Optional[UploadedDatasetEntity],
    ) -> Optional[UploadedDatasetEntity]:
        if row is None:
            return None
        return UploadedDatasetEntity(
            dataset_id=row.dataset_id,
            owner_id=row.owner_id,
            conversation_id=row.conversation_id,
            database_name=row.database_name,
            database_path=row.database_path,
            batch_dir=row.batch_dir,
            manifest_json=row.manifest_json,
            relationships_json=row.relationships_json,
            status=row.status,
            error_message=row.error_message,
            gmt_created=row.gmt_created,
            gmt_modified=row.gmt_modified,
        )


class UploadedDatasetService:
    """Register, authorize and preview an uploaded dataset."""

    def __init__(self, dao: Optional[UploadedDatasetDao] = None):
        self._dao = dao or UploadedDatasetDao()

    def register_ready(
        self,
        *,
        dataset_id: str,
        owner_id: str,
        conversation_id: str,
        database_name: str,
        database_path: Path,
        batch_dir: Path,
        files: Sequence[Dict[str, Any]],
        relationships: Sequence[Dict[str, Any]],
    ) -> AuthorizedUploadedDataset:
        if not conversation_id or len(conversation_id) > 255:
            raise ValueError("A bounded conversation id is required for uploads")
        if not owner_id:
            raise ValueError("An authenticated owner is required for uploads")

        resolved_batch = batch_dir.resolve()
        resolved_database = database_path.resolve()
        _require_inside(resolved_database, resolved_batch)
        normalized_files: List[Dict[str, Any]] = []
        for item in files:
            stored_path = Path(str(item.get("stored_path") or "")).resolve()
            _require_inside(stored_path, resolved_batch)
            if not stored_path.is_file():
                raise ValueError(f"Uploaded file is missing: {item.get('name')}")
            normalized = dict(item)
            normalized["stored_path"] = str(stored_path)
            normalized_files.append(normalized)

        self._dao.create_dataset(
            {
                "dataset_id": dataset_id,
                "owner_id": owner_id,
                "conversation_id": conversation_id,
                "database_name": database_name,
                "database_path": str(resolved_database),
                "batch_dir": str(resolved_batch),
                "manifest_json": json.dumps(normalized_files, ensure_ascii=False),
                "relationships_json": json.dumps(
                    list(relationships), ensure_ascii=False
                ),
                "status": "ready",
            }
        )
        return self.resolve_owned(dataset_id, owner_id, conversation_id)

    def resolve_owned(
        self,
        dataset_id: str,
        owner_id: str,
        conversation_id: Optional[str] = None,
        *,
        replay_task_id: Optional[str] = None,
    ) -> AuthorizedUploadedDataset:
        row = self._dao.get_owned(dataset_id, owner_id)
        if row is None:
            raise UploadedDatasetNotFoundError("Uploaded dataset not found")
        if row.status != "ready":
            raise UploadedDatasetAccessError("Uploaded dataset is not ready")

        conversation_matches = bool(
            conversation_id and conversation_id == row.conversation_id
        )
        replay_allowed = bool(
            replay_task_id
            and self._task_authorizes_dataset(replay_task_id, owner_id, dataset_id)
        )
        if conversation_id is not None and not (conversation_matches or replay_allowed):
            raise UploadedDatasetNotFoundError("Uploaded dataset not found")

        try:
            raw_files = json.loads(row.manifest_json or "[]")
            relationships = json.loads(row.relationships_json or "[]")
        except json.JSONDecodeError as exc:
            raise UploadedDatasetAccessError(
                "Uploaded dataset manifest is invalid"
            ) from exc
        if not isinstance(raw_files, list) or not raw_files:
            raise UploadedDatasetAccessError("Uploaded dataset manifest is empty")

        batch_dir = Path(row.batch_dir).resolve()
        database_path = Path(row.database_path).resolve()
        _require_inside(database_path, batch_dir)
        if not database_path.is_file():
            raise UploadedDatasetAccessError("Uploaded dataset database is missing")

        normalized_files: List[Dict[str, Any]] = []
        for item in raw_files:
            if not isinstance(item, dict):
                raise UploadedDatasetAccessError("Uploaded dataset manifest is invalid")
            stored_path = Path(str(item.get("stored_path") or "")).resolve()
            _require_inside(stored_path, batch_dir)
            if not stored_path.is_file():
                raise UploadedDatasetAccessError("An uploaded dataset file is missing")
            normalized = dict(item)
            normalized["stored_path"] = str(stored_path)
            normalized_files.append(normalized)

        return AuthorizedUploadedDataset(
            dataset_id=row.dataset_id,
            owner_id=row.owner_id,
            conversation_id=row.conversation_id,
            database_name=row.database_name,
            database_path=database_path,
            batch_dir=batch_dir,
            files=tuple(normalized_files),
            relationships=tuple(
                item for item in relationships if isinstance(item, dict)
            ),
        )

    def latest_for_conversation(
        self, owner_id: str, conversation_id: str
    ) -> Optional[AuthorizedUploadedDataset]:
        row = self._dao.get_latest_for_conversation(owner_id, conversation_id)
        if row is None:
            return None
        return self.resolve_owned(row.dataset_id, owner_id, conversation_id)

    def preview_file(
        self,
        dataset_id: str,
        file_id: str,
        owner_id: str,
        conversation_id: str,
        *,
        row_limit: int = 50,
    ) -> Dict[str, Any]:
        dataset = self.resolve_owned(dataset_id, owner_id, conversation_id)
        file_item = next(
            (item for item in dataset.files if item.get("file_id") == file_id), None
        )
        if file_item is None:
            raise UploadedDatasetNotFoundError("Uploaded file not found")
        return _preview_tabular_file(file_item, row_limit=max(1, min(row_limit, 100)))

    def delete_registry_record(self, dataset_id: str, owner_id: str) -> bool:
        return self._dao.delete_dataset(dataset_id, owner_id)

    @staticmethod
    def _task_authorizes_dataset(task_id: str, owner_id: str, dataset_id: str) -> bool:
        from dbgpt_serve.scheduled_task.dao.task_dao import ScheduledTaskDao

        task = ScheduledTaskDao().get_owned(task_id, owner_id)
        return bool(
            task
            and task.get("task_type") == "chat_replay"
            and task.get("resource_type") == "uploaded_dataset"
            and task.get("resource_id") == dataset_id
        )


def _require_inside(path: Path, parent: Path) -> None:
    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise UploadedDatasetAccessError(
            "Uploaded dataset path escapes its batch directory"
        ) from exc


def _preview_tabular_file(file_item: Dict[str, Any], row_limit: int) -> Dict[str, Any]:
    import pandas as pd

    path = Path(str(file_item["stored_path"]))
    suffix = path.suffix.casefold()
    sheet_name: Optional[str] = None
    if suffix in {".xls", ".xlsx"}:
        workbook = pd.ExcelFile(path)
        if not workbook.sheet_names:
            raise ValueError("Workbook contains no readable sheets")
        sheet_name = str(workbook.sheet_names[0])
        frame = pd.read_excel(path, sheet_name=sheet_name, nrows=row_limit)
    else:
        separator = "\t" if suffix == ".tsv" else ","
        last_error: Optional[Exception] = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
            try:
                frame = pd.read_csv(
                    path, sep=separator, encoding=encoding, nrows=row_limit
                )
                break
            except UnicodeDecodeError as exc:
                last_error = exc
        else:
            if last_error is not None:
                raise last_error
            raise ValueError("Unable to preview uploaded file")

    rows = json.loads(frame.to_json(orient="records", date_format="iso"))
    table_rows = [
        int(table.get("row_count") or 0)
        for table in file_item.get("tables", [])
        if isinstance(table, dict)
        and (sheet_name is None or table.get("source_sheet") == sheet_name)
    ]
    return {
        "file_id": file_item.get("file_id"),
        "file_name": file_item.get("name"),
        "kind": "table",
        "sheet_name": sheet_name,
        "columns": [str(column) for column in frame.columns],
        "rows": rows,
        "shape": [table_rows[0] if table_rows else len(rows), len(frame.columns)],
        "preview_row_count": len(rows),
        "truncated": bool(table_rows and table_rows[0] > len(rows)),
    }


def upload_work_dir() -> Path:
    """Return the configured DB-GPT work directory without trusting the client."""

    cfg = Config()
    if cfg.SYSTEM_APP and getattr(cfg.SYSTEM_APP, "work_dir", None):
        return Path(cfg.SYSTEM_APP.work_dir).resolve()
    return Path(os.getcwd()).resolve()


def validate_legacy_user_paths(raw_paths: Iterable[str], owner_id: str) -> List[str]:
    """Safely retain old/example snapshots without accepting arbitrary paths."""

    from dbgpt_app.openapi.api_v1.python_upload_api import (
        _resolve_upload_dir,
        _resolve_user_id,
    )

    safe_owner = _resolve_user_id(owner_id)
    owner_root = Path(_resolve_upload_dir(str(upload_work_dir()), safe_owner)).resolve()
    resolved: List[str] = []
    for raw_path in raw_paths:
        path = Path(raw_path).resolve()
        _require_inside(path, owner_root)
        if not path.is_file():
            raise UploadedDatasetNotFoundError("Uploaded file not found")
        resolved.append(str(path))
    return resolved
