"""Storage for knowledge source bindings and sync logs."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, String, Text

from dbgpt.storage.metadata import BaseDao, Model


class KnowledgeSourceEntity(Model):
    __tablename__ = "knowledge_source"

    id = Column(Integer, primary_key=True)
    space_id = Column(Integer, index=True)
    name = Column(String(128))
    type = Column(String(64))  # connector type (registry key)
    config = Column(Text)  # AES-GCM encrypted dict
    target_resource_ids = Column(Text)  # JSON list of external_id
    mapping_json = Column(Text)  # JSON external_id → doc_id
    interval_minutes = Column(Integer, default=0)  # 0 = manual only
    sync_mode = Column(String(16), default="incremental")
    conflict_strategy = Column(String(16), default="overwrite")
    sync_deletions = Column(Integer, default=0)
    status = Column(String(16), default="active")  # active|paused|running|error
    last_sync_at = Column(DateTime)
    last_sync_cursor = Column(Text)  # JSON SyncCursor snapshot
    last_sync_result = Column(Text)  # JSON summary
    error_message = Column(Text)
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)

    def to_dict(self, with_config: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "space_id": self.space_id,
            "name": self.name,
            "type": self.type,
            "target_resource_ids": json.loads(self.target_resource_ids)
            if self.target_resource_ids
            else [],
            "interval_minutes": self.interval_minutes or 0,
            "sync_mode": self.sync_mode,
            "conflict_strategy": self.conflict_strategy,
            "sync_deletions": bool(self.sync_deletions),
            "status": self.status,
            "last_sync_at": self.last_sync_at.isoformat()
            if self.last_sync_at
            else None,
            "has_cursor": bool(self.last_sync_cursor),
            "error_message": self.error_message,
            "gmt_modified": self.gmt_modified.isoformat()
            if self.gmt_modified
            else None,
        }
        return data


class KnowledgeSourceKeyEntity(Model):
    """Single-row keystore for the auto-provisioned encrypt key.

    Product default so the feature works zero-config: when the operator
    has not set an explicit key (env / toml), one is generated once and
    kept here. Trade-off documented in crypto.py — protection is
    best-effort; enterprises should still pin their own key.
    """

    __tablename__ = "knowledge_source_keystore"

    id = Column(Integer, primary_key=True)  # always 1
    key_text = Column(Text)
    gmt_created = Column(DateTime)
    gmt_modified = Column(DateTime)


class KnowledgeSourceSyncLogEntity(Model):
    __tablename__ = "knowledge_source_sync_log"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, index=True)
    space_id = Column(Integer, index=True)
    trigger = Column(String(16))  # manual | scheduler
    mode = Column(String(16))  # incremental | full
    items_created = Column(Integer, default=0)
    items_updated = Column(Integer, default=0)
    items_skipped = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    status = Column(String(16))  # success | failed
    error = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class KnowledgeSourceKeyDao(BaseDao):
    """Auto-provisioned key storage (created on first use)."""

    def get_or_create(self) -> str:
        import secrets

        session = self.get_raw_session()
        try:
            row = (
                session.query(KnowledgeSourceKeyEntity)
                .filter(KnowledgeSourceKeyEntity.id == 1)
                .first()
            )
            if row is None:
                row = KnowledgeSourceKeyEntity(
                    id=1,
                    key_text=secrets.token_urlsafe(32),
                    gmt_created=datetime.now(),
                    gmt_modified=datetime.now(),
                )
                session.add(row)
                session.expire_on_commit = False
                session.commit()
                session.expunge(row)
            else:
                session.expire_on_commit = False
                session.expunge(row)
            return row.key_text or ""
        finally:
            session.close()


class KnowledgeSourceDao(BaseDao):
    """DAO for source bindings."""

    def create_source(self, values: Dict[str, Any]) -> KnowledgeSourceEntity:
        now = datetime.now()
        entity = KnowledgeSourceEntity(
            space_id=values["space_id"],
            name=values.get("name") or values.get("type"),
            type=values["type"],
            config=values["config"],
            target_resource_ids=values.get("target_resource_ids") or "[]",
            mapping_json="{}",
            interval_minutes=values.get("interval_minutes") or 0,
            sync_mode=values.get("sync_mode") or "incremental",
            conflict_strategy=values.get("conflict_strategy") or "overwrite",
            sync_deletions=1 if values.get("sync_deletions") else 0,
            status=values.get("status") or "active",
            gmt_created=now,
            gmt_modified=now,
        )
        session = self.get_raw_session()
        try:
            session.add(entity)
            session.expire_on_commit = False
            session.commit()
            session.expunge(entity)
        finally:
            session.close()
        return entity

    def get_source(self, source_id: int) -> Optional[KnowledgeSourceEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.id == source_id)
                .first()
            )
        finally:
            session.close()

    def list_by_space(self, space_id: int) -> List[KnowledgeSourceEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.space_id == space_id)
                .order_by(KnowledgeSourceEntity.id.asc())
                .all()
            )
        finally:
            session.close()

    def update_source(self, source_id: int, updates: Dict[str, Any]) -> None:
        session = self.get_raw_session()
        try:
            row = (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.id == source_id)
                .first()
            )
            if row is None:
                return
            for key, value in updates.items():
                if hasattr(row, key) and value is not None:
                    setattr(row, key, value)
            row.gmt_modified = datetime.now()
            session.commit()
        finally:
            session.close()

    def delete_source(self, source_id: int) -> bool:
        session = self.get_raw_session()
        try:
            row = (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.id == source_id)
                .first()
            )
            if row is None:
                return False
            session.query(KnowledgeSourceSyncLogEntity).filter(
                KnowledgeSourceSyncLogEntity.source_id == source_id
            ).delete()
            session.delete(row)
            session.commit()
            return True
        finally:
            session.close()

    # ---- sync bookkeeping -------------------------------------------------
    def try_claim(
        self, source_id: int, stale_after_minutes: int = 30
    ) -> Optional[KnowledgeSourceEntity]:
        """Atomically-ish claim a source for syncing (single worker P0)."""
        session = self.get_raw_session()
        try:
            row = (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.id == source_id)
                .first()
            )
            if row is None:
                return None
            now = datetime.now()
            if (
                row.status == "running"
                and row.gmt_modified
                and (now - row.gmt_modified < timedelta(minutes=stale_after_minutes))
            ):
                return None  # another run holds it
            row.status = "running"
            row.gmt_modified = now
            session.expire_on_commit = False
            session.commit()
            session.expunge(row)
            return row
        finally:
            session.close()

    def release_claim(
        self,
        source_id: int,
        ok: bool,
        cursor_json: Optional[str] = None,
        mapping_json: Optional[str] = None,
        result_json: Optional[str] = None,
        error: Optional[str] = None,
        is_error_state: bool = False,
    ) -> None:
        session = self.get_raw_session()
        try:
            row = (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.id == source_id)
                .first()
            )
            if row is None:
                return
            row.status = "error" if (error and is_error_state) else "active"
            if cursor_json is not None:
                row.last_sync_cursor = cursor_json
            if mapping_json is not None:
                row.mapping_json = mapping_json
            if result_json is not None:
                row.last_sync_result = result_json
            row.last_sync_at = datetime.now()
            row.error_message = error
            row.gmt_modified = datetime.now()
            session.commit()
        finally:
            session.close()

    def due_sources(self) -> List[KnowledgeSourceEntity]:
        """Active bindings with a schedule whose next run is due."""
        now = datetime.now()
        session = self.get_raw_session()
        try:
            rows = (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.status == "active")
                .filter(KnowledgeSourceEntity.interval_minutes > 0)
                .all()
            )
            due = []
            for row in rows:
                interval = timedelta(minutes=row.interval_minutes)
                if row.last_sync_at is None or now - row.last_sync_at >= interval:
                    due.append(row)
            return due
        finally:
            session.close()

    def recover_stale_running(self, stale_minutes: int = 30) -> int:
        deadline = datetime.now() - timedelta(minutes=stale_minutes)
        session = self.get_raw_session()
        try:
            rows = (
                session.query(KnowledgeSourceEntity)
                .filter(KnowledgeSourceEntity.status == "running")
                .all()
            )
            n = 0
            for row in rows:
                if row.gmt_modified and row.gmt_modified < deadline:
                    row.status = "active"
                    row.error_message = "recovered: sync process died mid-run"
                    row.gmt_modified = datetime.now()
                    n += 1
            if n:
                session.commit()
            return n
        finally:
            session.close()


class KnowledgeSourceSyncLogDao(BaseDao):
    def append(self, values: Dict[str, Any]) -> None:
        now = datetime.now()
        session = self.get_raw_session()
        try:
            session.add(
                KnowledgeSourceSyncLogEntity(
                    source_id=values["source_id"],
                    space_id=values["space_id"],
                    trigger=values.get("trigger") or "manual",
                    mode=values.get("mode") or "full",
                    items_created=values.get("items_created", 0),
                    items_updated=values.get("items_updated", 0),
                    items_skipped=values.get("items_skipped", 0),
                    items_failed=values.get("items_failed", 0),
                    status=values.get("status") or "success",
                    error=values.get("error"),
                    started_at=values.get("started_at") or now,
                    finished_at=values.get("finished_at") or now,
                )
            )
            session.commit()
        finally:
            session.close()

    def list_by_source(
        self, source_id: int, limit: int = 50
    ) -> List[KnowledgeSourceSyncLogEntity]:
        session = self.get_raw_session()
        try:
            return (
                session.query(KnowledgeSourceSyncLogEntity)
                .filter(KnowledgeSourceSyncLogEntity.source_id == source_id)
                .order_by(KnowledgeSourceSyncLogEntity.id.desc())
                .limit(limit)
                .all()
            )
        finally:
            session.close()

    def to_dict(self, log: KnowledgeSourceSyncLogEntity) -> Dict[str, Any]:
        return {
            "id": log.id,
            "source_id": log.source_id,
            "trigger": log.trigger,
            "mode": log.mode,
            "items_created": log.items_created,
            "items_updated": log.items_updated,
            "items_skipped": log.items_skipped,
            "items_failed": log.items_failed,
            "status": log.status,
            "error": log.error,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
        }
