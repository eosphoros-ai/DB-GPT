"""Entities / DAOs for the plugins (expert suite) module.

Table names follow the module (``dbgpt_serve_plugins*``); the domain object is
a suite, hence the ``Suite*`` class names (see config.py header note).
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import Column, DateTime, Index, Integer, String, Text, UniqueConstraint

from dbgpt.storage.metadata import BaseDao, Model

from ..api.schemas import SuiteEventResponse, SuiteRequest, SuiteResponse
from ..config import SERVER_APP_TABLE_NAME, SERVER_EVENT_TABLE_NAME, ServeConfig

logger = logging.getLogger(__name__)


class SuiteEntity(Model):
    """Install / enable registry row.  Content lives in the package, not here."""

    __tablename__ = SERVER_APP_TABLE_NAME
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    name = Column(String(255), nullable=False, comment="suite slug, e.g. db-query")
    display = Column(String(255), nullable=True, comment="display name")
    icon = Column(String(64), nullable=True, comment="icon emoji")
    scenario_id = Column(String(64), index=True, nullable=True)
    version = Column(String(64), nullable=False, comment="installed/active version")
    source = Column(
        String(32),
        nullable=False,
        default="official",
        comment="official|enterprise|market",
    )
    execution = Column(String(16), nullable=True, default="react", comment="react|flow")
    status = Column(
        String(16),
        nullable=False,
        default="installed",
        comment="installed|enabled|disabled",
    )
    workspace_id = Column(
        String(128), index=True, nullable=True, comment="instance scope; NULL=global"
    )
    package_path = Column(String(512), nullable=True, comment="package location")
    package_digest = Column(
        String(64), nullable=True, comment="sha256 for drift detect"
    )
    manifest_snapshot = Column(Text, nullable=True, comment="derived JSON projection")
    use_count = Column(Integer, nullable=True, default=0, comment="pin/invoke count")
    enabled_at = Column(DateTime, nullable=True, comment="last enabled time")
    user_name = Column(String(255), nullable=True, comment="installer/owner")
    sys_code = Column(String(128), index=True, nullable=True, comment="system code")
    gmt_created = Column(DateTime, default=datetime.utcnow, comment="install time")
    gmt_modified = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="update time",
    )

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uk_plugins_ws_name"),
        Index("idx_plugins_scenario", "scenario_id"),
        Index("idx_plugins_status", "status"),
    )

    def __repr__(self):  # pragma: no cover - debug helper
        return (
            f"SuiteEntity(id={self.id}, name='{self.name}', version='{self.version}', "
            f"status='{self.status}', workspace_id='{self.workspace_id}')"
        )


class SuiteEventEntity(Model):
    """Audit / timeline events: install/enable/disable/upgrade/switch/pin."""

    __tablename__ = SERVER_EVENT_TABLE_NAME
    id = Column(Integer, primary_key=True, comment="autoincrement id")
    suite_name = Column(String(255), nullable=False, index=True, comment="suite slug")
    event_type = Column(String(32), nullable=False, index=True)
    from_version = Column(String(64), nullable=True)
    to_version = Column(String(64), nullable=True)
    conv_uid = Column(
        String(128), index=True, nullable=True, comment="switch/pin events"
    )
    workspace_id = Column(String(128), index=True, nullable=True)
    detail = Column(Text, nullable=True, comment="JSON payload")
    user_name = Column(String(255), nullable=True)
    sys_code = Column(String(128), index=True, nullable=True)
    gmt_created = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):  # pragma: no cover - debug helper
        return (
            f"SuiteEventEntity(id={self.id}, suite_name='{self.suite_name}', "
            f"event_type='{self.event_type}', conv_uid='{self.conv_uid}')"
        )


def _snapshot_to_json(snapshot: Optional[Dict[str, Any]]) -> Optional[str]:
    if snapshot is None:
        return None
    return json.dumps(snapshot, ensure_ascii=False, default=str)


def _snapshot_from_json(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001 - corrupt snapshot must not break listing
        logger.warning("manifest_snapshot is not valid JSON, ignored")
        return None


class SuiteDao(BaseDao[SuiteEntity, SuiteRequest, SuiteResponse]):
    """DAO for the install / enable registry."""

    def __init__(self, serve_config: Optional[ServeConfig] = None):
        super().__init__()
        self._serve_config = serve_config

    # -- BaseDao contract --------------------------------------------------
    def from_request(self, request: Union[SuiteRequest, Dict[str, Any]]) -> SuiteEntity:
        if isinstance(request, SuiteRequest):
            request = request.model_dump()
        return SuiteEntity(
            name=request.get("name"),
            workspace_id=request.get("workspace_id"),
            user_name=request.get("user_name"),
        )

    def to_request(self, entity: SuiteEntity) -> SuiteRequest:
        return SuiteRequest(
            name=entity.name,
            workspace_id=entity.workspace_id,
            user_name=entity.user_name,
        )

    def to_response(self, entity: SuiteEntity) -> SuiteResponse:
        return SuiteResponse(
            id=entity.id,
            name=entity.name,
            display=entity.display,
            icon=entity.icon,
            scenario_id=entity.scenario_id,
            version=entity.version,
            source=entity.source,
            execution=entity.execution,
            status=entity.status,
            workspace_id=entity.workspace_id,
            package_path=entity.package_path,
            package_digest=entity.package_digest,
            manifest_snapshot=_snapshot_from_json(entity.manifest_snapshot),
            use_count=entity.use_count,
            enabled_at=entity.enabled_at,
            user_name=entity.user_name,
            gmt_created=entity.gmt_created,
            gmt_modified=entity.gmt_modified,
        )

    # -- custom queries ----------------------------------------------------
    def get_by_name(
        self, name: str, workspace_id: Optional[str] = None
    ) -> Optional[SuiteEntity]:
        with self.session() as session:
            query = session.query(SuiteEntity).filter(SuiteEntity.name == name)
            if workspace_id is not None:
                query = query.filter(SuiteEntity.workspace_id == workspace_id)
            else:
                query = query.filter(SuiteEntity.workspace_id.is_(None))
            row = query.first()
            if row is not None:
                session.expunge(row)
            return row

    def list_all(self, workspace_id: Optional[str] = None) -> List[SuiteEntity]:
        with self.session() as session:
            query = session.query(SuiteEntity)
            if workspace_id is not None:
                query = query.filter(
                    (SuiteEntity.workspace_id == workspace_id)
                    | (SuiteEntity.workspace_id.is_(None))
                )
            rows = query.order_by(SuiteEntity.name).all()
            for row in rows:
                session.expunge(row)
            return rows

    def list_by_source(self, source: str) -> List[SuiteEntity]:
        with self.session() as session:
            rows = (
                session.query(SuiteEntity)
                .filter(SuiteEntity.source == source)
                .order_by(SuiteEntity.name)
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows

    def insert_official(
        self, pkg, status: str, user_name: str, source: str = "official"
    ) -> SuiteEntity:
        """Insert a registry row for a freshly discovered package."""
        entity = SuiteEntity(
            name=pkg.name,
            display=pkg.manifest.get("display"),
            icon=pkg.manifest.get("icon"),
            scenario_id=pkg.manifest.get("scenario_id"),
            version=pkg.version,
            source=source,
            execution=pkg.manifest.get("execution", "react"),
            status=status,
            workspace_id=None,
            package_path=pkg.path,
            package_digest=pkg.digest,
            manifest_snapshot=_snapshot_to_json(pkg.snapshot),
            use_count=0,
            enabled_at=datetime.utcnow() if status == "enabled" else None,
            user_name=user_name,
        )
        with self.session() as session:
            session.add(entity)
            session.flush()
            session.expunge(entity)
        return entity

    def update_package(self, entity: SuiteEntity, pkg, user_name: str) -> None:
        with self.session() as session:
            row = session.query(SuiteEntity).filter(SuiteEntity.id == entity.id).first()
            row.version = pkg.version
            row.display = pkg.manifest.get("display") or row.display
            row.icon = pkg.manifest.get("icon") or row.icon
            row.scenario_id = pkg.manifest.get("scenario_id") or row.scenario_id
            row.execution = pkg.manifest.get("execution", "react")
            row.package_path = pkg.path
            row.package_digest = pkg.digest
            row.manifest_snapshot = _snapshot_to_json(pkg.snapshot)
            row.user_name = user_name or row.user_name

    def set_status(
        self,
        name: str,
        status: str,
        workspace_id: Optional[str] = None,
        user_name: Optional[str] = None,
    ) -> None:
        with self.session() as session:
            query = session.query(SuiteEntity).filter(SuiteEntity.name == name)
            if workspace_id is not None:
                query = query.filter(SuiteEntity.workspace_id == workspace_id)
            else:
                query = query.filter(SuiteEntity.workspace_id.is_(None))
            row = query.first()
            if row is None:
                return
            row.status = status
            if status == "enabled":
                row.enabled_at = datetime.utcnow()
            if user_name:
                row.user_name = user_name

    def bump_use_count(self, name: str) -> None:
        with self.session() as session:
            row = (
                session.query(SuiteEntity)
                .filter(SuiteEntity.name == name, SuiteEntity.workspace_id.is_(None))
                .first()
            )
            if row is not None:
                row.use_count = (row.use_count or 0) + 1

    def delete_by_id(self, entity_id: int) -> None:
        with self.session() as session:
            row = session.query(SuiteEntity).filter(SuiteEntity.id == entity_id).first()
            if row is not None:
                session.delete(row)


class SuiteEventDao(BaseDao[SuiteEventEntity, SuiteRequest, SuiteEventResponse]):
    """DAO for audit / timeline events."""

    def __init__(self, serve_config: Optional[ServeConfig] = None):
        super().__init__()
        self._serve_config = serve_config

    # -- BaseDao contract --------------------------------------------------
    def from_request(
        self, request: Union[SuiteRequest, Dict[str, Any]]
    ) -> SuiteEventEntity:
        if isinstance(request, SuiteRequest):
            request = request.model_dump()
        return SuiteEventEntity(
            suite_name=request.get("name") or "",
            event_type="install",
            user_name=request.get("user_name"),
            workspace_id=request.get("workspace_id"),
        )

    def to_request(self, entity: SuiteEventEntity) -> SuiteRequest:
        return SuiteRequest(
            name=entity.suite_name,
            workspace_id=entity.workspace_id,
            user_name=entity.user_name,
        )

    def to_response(self, entity: SuiteEventEntity) -> SuiteEventResponse:
        return SuiteEventResponse(
            id=entity.id,
            suite_name=entity.suite_name,
            event_type=entity.event_type,
            from_version=entity.from_version,
            to_version=entity.to_version,
            conv_uid=entity.conv_uid,
            workspace_id=entity.workspace_id,
            detail=_snapshot_from_json(entity.detail),
            user_name=entity.user_name,
            gmt_created=entity.gmt_created,
        )

    # -- custom queries ----------------------------------------------------
    def add_event(
        self,
        suite_name: str,
        event_type: str,
        from_version: Optional[str] = None,
        to_version: Optional[str] = None,
        conv_uid: Optional[str] = None,
        workspace_id: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        user_name: Optional[str] = None,
    ) -> SuiteEventEntity:
        entity = SuiteEventEntity(
            suite_name=suite_name,
            event_type=event_type,
            from_version=from_version,
            to_version=to_version,
            conv_uid=conv_uid,
            workspace_id=workspace_id,
            detail=_snapshot_to_json(detail),
            user_name=user_name,
        )
        with self.session() as session:
            session.add(entity)
            session.flush()
            session.expunge(entity)
        return entity

    def list_by_suite(
        self, suite_name: str, limit: int = 100
    ) -> List[SuiteEventEntity]:
        with self.session() as session:
            rows = (
                session.query(SuiteEventEntity)
                .filter(SuiteEventEntity.suite_name == suite_name)
                .order_by(SuiteEventEntity.gmt_created.desc())
                .limit(limit)
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows

    def list_by_conv(self, conv_uid: str) -> List[SuiteEventEntity]:
        with self.session() as session:
            rows = (
                session.query(SuiteEventEntity)
                .filter(SuiteEventEntity.conv_uid == conv_uid)
                .order_by(SuiteEventEntity.gmt_created.asc())
                .all()
            )
            for row in rows:
                session.expunge(row)
            return rows
