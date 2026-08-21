"""Repository operations for session-scoped files."""

import re
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import func

from dbgpt.storage.metadata import BaseDao

from ..domain import (
    FileScope,
    SessionFileManifest,
    SessionFilePrivateRecord,
    SessionFileSnapshot,
    SessionFileStatus,
)
from .models import SessionFileEntity


class SessionFileDao(BaseDao[SessionFileEntity, Dict[str, Any], SessionFileManifest]):
    """Store private file locations while exposing only public metadata."""

    def from_request(self, request: Union[Dict[str, Any], Any]) -> SessionFileEntity:
        if isinstance(request, dict):
            request_dict = request
        elif hasattr(request, "model_dump"):
            request_dict = request.model_dump()
        else:
            request_dict = request.dict()
        return SessionFileEntity(**request_dict)

    def create(self, request: Union[Dict[str, Any], Any]) -> SessionFileManifest:
        """Validate scope and insert without using unrestricted BaseDao lookup."""
        entity = self.from_request(request)
        self._validate_entity(entity)
        with self.session() as session:
            session.add(entity)
            session.flush()
            return self.to_manifest(entity)

    def to_response(self, entity: SessionFileEntity) -> SessionFileManifest:
        """Map fields explicitly so private storage never crosses this boundary."""
        return self.to_manifest(entity)

    @staticmethod
    def to_manifest(entity: SessionFileEntity) -> SessionFileManifest:
        """Build agent-safe file metadata from a persistence record."""
        return SessionFileManifest(
            file_id=entity.file_id,
            name=entity.display_name,
            size=entity.size_bytes,
            media_type=entity.media_type,
            kind=entity.file_kind,
            status=SessionFileStatus(entity.status),
            ordinal=entity.ordinal,
        )

    @staticmethod
    def to_snapshot(entity: SessionFileEntity) -> SessionFileSnapshot:
        """Build history-safe file metadata from a persistence record."""
        return SessionFileSnapshot(
            file_id=entity.file_id,
            name=entity.display_name,
            size=entity.size_bytes,
            media_type=entity.media_type,
            kind=entity.file_kind,
            status=SessionFileStatus(entity.status),
            ordinal=entity.ordinal,
        )

    @staticmethod
    def to_private_record(entity: SessionFileEntity) -> SessionFilePrivateRecord:
        """Detach complete private metadata into an immutable domain value."""
        return SessionFilePrivateRecord(
            file_id=entity.file_id,
            owner_id=entity.owner_id,
            session_id=entity.session_id,
            task_id=entity.task_id,
            display_name=entity.display_name,
            storage_uri=entity.storage_uri,
            media_type=entity.media_type,
            file_kind=entity.file_kind,
            size_bytes=entity.size_bytes,
            sha256=entity.sha256,
            ordinal=entity.ordinal,
            status=SessionFileStatus(entity.status),
            inspection_json=entity.inspection_json,
            error_code=entity.error_code,
            error_message=entity.error_message,
            source_file_id=entity.source_file_id,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def get_by_file_id(
        self, file_id: str, scope: FileScope
    ) -> Optional[SessionFileManifest]:
        """Return a file only when owner and scope match, otherwise ``None``."""
        with self.session(commit=False) as session:
            entity = (
                self._scope_query(session, scope)
                .filter(SessionFileEntity.file_id == file_id)
                .first()
            )
            return self.to_manifest(entity) if entity is not None else None

    def get_private_file_by_id(
        self, file_id: str, scope: FileScope
    ) -> Optional[SessionFilePrivateRecord]:
        """Return immutable private metadata for an exact owner-bound scope."""
        with self.session(commit=False) as session:
            entity = (
                self._scope_query(session, scope)
                .filter(SessionFileEntity.file_id == file_id)
                .first()
            )
            return self.to_private_record(entity) if entity is not None else None

    def list_by_scope(self, scope: FileScope) -> List[SessionFileManifest]:
        """List an owner's scoped files in stable upload order."""
        with self.session(commit=False) as session:
            entities = (
                self._scope_query(session, scope)
                .order_by(SessionFileEntity.ordinal)
                .all()
            )
            return [self.to_manifest(entity) for entity in entities]

    def list_by_source_file_id(
        self, source_file_id: str, scope: FileScope
    ) -> List[SessionFileManifest]:
        """List lineage records within one exact owner-bound scope."""
        with self.session(commit=False) as session:
            entities = (
                self._scope_query(session, scope)
                .filter(SessionFileEntity.source_file_id == source_file_id)
                .order_by(SessionFileEntity.ordinal)
                .all()
            )
            return [self.to_manifest(entity) for entity in entities]

    def total_size_bytes(self, scope: FileScope) -> int:
        """Return total persisted bytes for one owner-bound scope."""
        with self.session(commit=False) as session:
            total = (
                self._scope_query(session, scope)
                .with_entities(func.coalesce(func.sum(SessionFileEntity.size_bytes), 0))
                .scalar()
            )
            return int(total)

    def total_owner_size_bytes(self, owner_id: str) -> int:
        """Return total persisted bytes across all scopes for one owner."""
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("owner_id must not be blank")
        with self.session(commit=False) as session:
            total = (
                session.query(func.coalesce(func.sum(SessionFileEntity.size_bytes), 0))
                .filter(SessionFileEntity.owner_id == owner_id)
                .scalar()
            )
            return int(total)

    def update_status(
        self,
        file_id: str,
        scope: FileScope,
        status: Union[SessionFileStatus, str],
        inspection_json: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[SessionFileManifest]:
        """Update processing state only for the exact owner-bound scope."""
        status_value = self._validate_status(status)
        with self.session() as session:
            entity = (
                self._scope_query(session, scope)
                .filter(SessionFileEntity.file_id == file_id)
                .first()
            )
            if entity is None:
                return None
            entity.status = status_value
            entity.inspection_json = inspection_json
            entity.error_code = error_code
            entity.error_message = error_message
            session.flush()
            return self.to_manifest(entity)

    def delete_by_file_id(self, file_id: str, scope: FileScope) -> bool:
        """Delete a file only for the exact owner-bound scope."""
        with self.session() as session:
            deleted = (
                self._scope_query(session, scope)
                .filter(SessionFileEntity.file_id == file_id)
                .delete(synchronize_session=False)
            )
            return deleted == 1

    def get_one(self, *args, **kwargs):
        raise NotImplementedError("Use a scope-constrained session file method")

    def get_list(self, *args, **kwargs):
        raise NotImplementedError("Use a scope-constrained session file method")

    def get_list_page(self, *args, **kwargs):
        raise NotImplementedError("Use a scope-constrained session file method")

    def update(self, *args, **kwargs):
        raise NotImplementedError("Use a scope-constrained session file method")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Use a scope-constrained session file method")

    @staticmethod
    def _validate_entity(entity: SessionFileEntity) -> None:
        FileScope(
            owner_id=entity.owner_id,
            session_id=entity.session_id,
            task_id=entity.task_id,
        )
        SessionFileDao._validate_status(entity.status)
        if entity.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        if entity.ordinal < 0:
            raise ValueError("ordinal must be non-negative")
        if (
            not isinstance(entity.sha256, str)
            or re.fullmatch(r"[0-9a-fA-F]{64}", entity.sha256) is None
        ):
            raise ValueError("sha256 must contain exactly 64 hexadecimal characters")

    @staticmethod
    def _validate_status(status: Union[SessionFileStatus, str]) -> str:
        try:
            return SessionFileStatus(status).value
        except (TypeError, ValueError) as error:
            raise ValueError("invalid session file status") from error

    @staticmethod
    def _scope_query(session, scope: FileScope):
        query = session.query(SessionFileEntity).filter(
            SessionFileEntity.owner_id == scope.owner_id
        )
        if scope.session_id is not None:
            return query.filter(
                SessionFileEntity.session_id == scope.session_id,
                SessionFileEntity.task_id.is_(None),
            )
        return query.filter(
            SessionFileEntity.task_id == scope.task_id,
            SessionFileEntity.session_id.is_(None),
        )
