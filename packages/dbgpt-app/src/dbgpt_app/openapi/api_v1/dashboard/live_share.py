"""Explicit live-data grants. Published configuration is fixed; data is renewable.

Anonymous visitors can only filter a bounded, owner-authorized materialization.
They cannot submit SQL, select a source, force a refresh, or modify a draft.
"""

import hashlib
import json
import secrets
import threading
from datetime import datetime, timedelta

from sqlalchemy import Column, DateTime, Integer, String

from dbgpt.storage.metadata import Model

from .models import DashboardNotFoundError, _json_text_type
from .publication import DashboardPublicationError
from .schemas import (
    DashboardAction,
    DashboardSnapshot,
    PublicDashboardSnapshot,
    model_dump_compat,
)
from .share_vault import (
    DashboardShareSecretEntity,
    public_origin,
    recover_share_token,
    share_cipher,
)

REFRESH_SECONDS = 60
_locks = [threading.Lock() for _ in range(16)]


class DashboardLiveShareEntity(Model):
    __tablename__ = "dbgpt_dashboard_live_share"
    dashboard_id = Column(String(64), primary_key=True)
    token_hash = Column(String(64), nullable=False, unique=True)
    owner_id = Column(String(255), nullable=False)
    revision = Column(Integer, nullable=False)
    schema_json = Column(_json_text_type(), nullable=False)
    cache_json = Column(_json_text_type(), nullable=False)
    gmt_created = Column(DateTime, nullable=False)
    last_attempt_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class LiveShareService:
    def __init__(self, dashboard_service):
        self.service = dashboard_service
        self.dao = dashboard_service.dao

    def _remember_token(self, session, digest, token):
        stored = (
            session.query(DashboardShareSecretEntity)
            .filter_by(token_hash=digest)
            .first()
        )
        if stored is None:
            session.add(
                DashboardShareSecretEntity(
                    token_hash=digest,
                    ciphertext=share_cipher().encrypt(token.encode()).decode(),
                )
            )

    def _materialize(self, schema, dashboard_id):
        datasets = self.service.publication_service.materialize(
            schema, self.service.query_executor
        )
        snapshot = DashboardSnapshot(
            dashboard_id=dashboard_id,
            refreshed_at=datetime.now(),
            filters={},
            widgets={},
            publication_datasets=datasets,
        )
        # Validate every widget and default filter before issuing a public grant.
        response = self.service.publication_service.filter_snapshot(
            schema, snapshot, {}
        )
        if response.unsupported_widget_ids:
            raise DashboardPublicationError("请先为所有组件配置分享筛选字段。")
        return snapshot

    def create(self, dashboard_id, actor):
        self.service.require_permission(dashboard_id, actor, DashboardAction.PUBLISH)
        revision = self.dao.get_latest_published_revision(dashboard_id)
        if revision is None:
            raise DashboardPublicationError("请先发布看板，再生成持续更新链接。")
        schema = self.service._parse_schema(revision.schema_json)
        self.service.require_permission(
            dashboard_id, actor, DashboardAction.QUERY, schema
        )
        snapshot = self._materialize(schema, dashboard_id)
        token = "live_" + secrets.token_urlsafe(32)
        now = datetime.now()
        with self.dao.session() as session:
            row = (
                session.query(DashboardLiveShareEntity)
                .filter_by(dashboard_id=dashboard_id)
                .with_for_update()
                .first()
            )
            if row is None:
                row = DashboardLiveShareEntity(dashboard_id=dashboard_id)
                session.add(row)
            else:
                session.query(DashboardShareSecretEntity).filter_by(
                    token_hash=row.token_hash
                ).delete(synchronize_session=False)
            row.token_hash = hashlib.sha256(token.encode()).hexdigest()
            row.owner_id = actor
            row.revision = revision.revision
            row.schema_json = revision.schema_json
            row.cache_json = json.dumps(model_dump_compat(snapshot), ensure_ascii=False)
            row.gmt_created = row.last_attempt_at = now
            row.expires_at = now + timedelta(days=30)
            row.revoked_at = None
            self._remember_token(session, row.token_hash, token)
        self.service._audit(
            dashboard_id,
            actor,
            "dashboard.live_share_created",
            details={"revision": revision.revision},
        )
        return {
            "share_path": "/dashboard-share/" + token,
            "expires_at": now + timedelta(days=30),
            "published_revision": revision.revision,
            "refresh_interval": REFRESH_SECONDS,
            "public_base_url": public_origin(),
        }

    def status(self, dashboard_id, actor):
        self.service.require_permission(dashboard_id, actor, DashboardAction.PUBLISH)
        latest = self.dao.get_latest_published_revision(dashboard_id)
        now = datetime.now()
        fixed_token = None
        if latest:
            for grant in self.dao.list_shares(dashboard_id):
                if (
                    grant.revision == latest.revision
                    and grant.revoked_at is None
                    and (grant.expires_at is None or grant.expires_at > now)
                ):
                    fixed_token = recover_share_token(self.dao, grant.token_hash)
                    break
        with self.dao.session(commit=False) as session:
            row = (
                session.query(DashboardLiveShareEntity)
                .filter_by(dashboard_id=dashboard_id)
                .first()
            )
            active = bool(
                row and not row.revoked_at and row.expires_at > datetime.now()
            )
            share_path = None
            if active:
                stored = (
                    session.query(DashboardShareSecretEntity)
                    .filter_by(token_hash=row.token_hash)
                    .first()
                )
                if stored:
                    try:
                        token = (
                            share_cipher().decrypt(stored.ciphertext.encode()).decode()
                        )
                        if hashlib.sha256(token.encode()).hexdigest() == row.token_hash:
                            share_path = "/dashboard-share/" + token
                    except Exception:
                        # Missing deployment keys must not rotate or revoke
                        # a working grant.
                        pass
            return {
                "active": active,
                "share_path": share_path,
                "public_base_url": public_origin(),
                "snapshot_share_path": "/dashboard-share/" + fixed_token
                if fixed_token
                else None,
                "expires_at": row.expires_at if row else None,
                "published_revision": row.revision if row else None,
            }

    def revoke(self, dashboard_id, actor):
        self.service.require_permission(dashboard_id, actor, DashboardAction.PUBLISH)
        with self.dao.session() as session:
            row = (
                session.query(DashboardLiveShareEntity)
                .filter_by(dashboard_id=dashboard_id)
                .with_for_update()
                .first()
            )
            if row is not None:
                session.query(DashboardShareSecretEntity).filter_by(
                    token_hash=row.token_hash
                ).delete(synchronize_session=False)
                row.revoked_at = datetime.now()
        self.service._audit(dashboard_id, actor, "dashboard.live_share_revoked")
        return {"revoked": True}

    def read(self, token, filters=None):
        digest = hashlib.sha256(token.encode()).hexdigest()
        # Fixed-size lock stripes bound concurrent upstream work in this process;
        # The row lock also coalesces refreshes across database-backed workers.
        with _locks[int(digest[:4], 16) % len(_locks)], self.dao.session() as session:
            row = (
                session.query(DashboardLiveShareEntity)
                .filter_by(token_hash=digest)
                .with_for_update()
                .first()
            )
            now = datetime.now()
            if row is None or row.revoked_at or row.expires_at <= now:
                raise DashboardNotFoundError("持续更新分享不存在或已失效")
            # An existing pre-v9.5 link can recover its encrypted copy on a valid visit.
            self._remember_token(session, digest, token)
            schema = self.service._parse_schema(row.schema_json)
            # Recheck the granting user's current source permissions even on cache hits.
            self.service.require_permission(
                row.dashboard_id, row.owner_id, DashboardAction.QUERY, schema
            )
            cached_payload = json.loads(row.cache_json)
            failed = bool(cached_payload.pop("_refresh_failed", False))
            cached = DashboardSnapshot.model_validate(cached_payload)
            if (now - row.last_attempt_at).total_seconds() >= REFRESH_SECONDS:
                row.last_attempt_at = now
                try:
                    cached = self._materialize(schema, row.dashboard_id)
                    row.cache_json = json.dumps(
                        model_dump_compat(cached), ensure_ascii=False
                    )
                    failed = False
                except Exception:
                    # Do not reveal connector details or advertise old data as fresh.
                    failed = True
                    row.cache_json = json.dumps(
                        {**model_dump_compat(cached), "_refresh_failed": True},
                        ensure_ascii=False,
                    )
            stale = (
                failed
                or (row.last_attempt_at - cached.refreshed_at).total_seconds() > 1
                or (now - cached.refreshed_at).total_seconds() > REFRESH_SECONDS * 2
            )
            filtered = self.service.publication_service.filter_snapshot(
                schema, cached, filters or {}
            )
            return PublicDashboardSnapshot(
                dashboard_id=row.dashboard_id,
                published_revision=row.revision,
                schema=schema,
                snapshot=filtered.snapshot,
                published_at=row.gmt_created,
                data_mode="live",
                refresh_interval=REFRESH_SECONDS,
                stale=stale,
                refresh_error=(
                    "数据源暂时无法更新，正在显示上次成功的数据。" if stale else None
                ),
            )
