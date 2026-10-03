"""SQLAlchemy entities and persistence operations for dashboards."""

import json
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    or_,
)
from sqlalchemy.dialects.mysql import LONGTEXT

from dbgpt.storage.metadata import BaseDao, Model


def _json_text_type():
    """Use MySQL LONGTEXT for snapshots while keeping portable TEXT elsewhere."""

    return Text().with_variant(LONGTEXT(), "mysql")


class DashboardNotFoundError(LookupError):
    pass


class DashboardConflictError(RuntimeError):
    pass


class DashboardAccessDeniedError(PermissionError):
    pass


class DashboardEntity(Model):
    __tablename__ = "dbgpt_dashboard"

    id = Column(String(64), primary_key=True)
    owner_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(String(255), nullable=True, index=True)
    source_turn_id = Column(String(64), nullable=True, index=True)
    origin = Column(String(32), nullable=False, default="manual", index=True)
    asset_state = Column(String(32), nullable=False, default="saved", index=True)
    saved_at = Column(DateTime, nullable=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    data_source_id = Column(String(255), nullable=False)
    schema_json = Column(_json_text_type(), nullable=False)
    current_revision = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False, default="draft")
    public_slug = Column(String(64), nullable=True, unique=True, index=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class DashboardEditVersionEntity(Model):
    """Append-only schema snapshot for every persisted edit revision."""

    __tablename__ = "dbgpt_dashboard_edit_version"
    __table_args__ = (
        UniqueConstraint("dashboard_id", "revision", name="uk_dashboard_edit_version"),
    )

    id = Column(
        Integer().with_variant(BigInteger(), "mysql"),
        primary_key=True,
        autoincrement=True,
    )
    dashboard_id = Column(String(64), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    schema_json = Column(_json_text_type(), nullable=False)
    source = Column(String(64), nullable=False, default="manual_edit", index=True)
    actor_id = Column(String(255), nullable=False, index=True)
    operation_id = Column(String(64), nullable=True, index=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now, index=True)


class DashboardRevisionEntity(Model):
    __tablename__ = "dbgpt_dashboard_revision"
    __table_args__ = (
        UniqueConstraint(
            "dashboard_id", "revision", name="uk_dashboard_published_revision"
        ),
        UniqueConstraint("share_token_hash", name="uk_dashboard_share_token_hash"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dashboard_id = Column(String(64), nullable=False, index=True)
    revision = Column(Integer, nullable=False)
    schema_json = Column(_json_text_type(), nullable=False)
    snapshot_json = Column(_json_text_type(), nullable=False)
    validation_json = Column(_json_text_type(), nullable=False)
    share_token_hash = Column(String(64), nullable=False, index=True)
    gmt_published = Column(DateTime, nullable=False, default=datetime.now)


class DashboardShareEntity(Model):
    """Revocable access token for one immutable published revision."""

    __tablename__ = "dbgpt_dashboard_share"
    __table_args__ = (UniqueConstraint("token_hash", name="uk_dashboard_share_token"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    dashboard_id = Column(String(64), nullable=False, index=True)
    revision = Column(Integer, nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)
    created_by = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)


class DashboardMemberEntity(Model):
    """Dashboard-scoped role assignment."""

    __tablename__ = "dbgpt_dashboard_member"
    __table_args__ = (
        UniqueConstraint(
            "dashboard_id", "principal_id", name="uk_dashboard_member_principal"
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    dashboard_id = Column(String(64), nullable=False, index=True)
    principal_id = Column(String(255), nullable=False, index=True)
    role = Column(String(32), nullable=False)
    created_by = Column(String(255), nullable=False)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


class DashboardAuditEntity(Model):
    """Append-only audit event without result rows or secret parameter values."""

    __tablename__ = "dbgpt_dashboard_audit"

    id = Column(
        Integer().with_variant(BigInteger(), "mysql"),
        primary_key=True,
        autoincrement=True,
    )
    dashboard_id = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(255), nullable=False, index=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=False, default="dashboard")
    target_id = Column(String(255), nullable=True)
    details_json = Column(_json_text_type(), nullable=False, default="{}")
    request_id = Column(String(64), nullable=True, index=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now, index=True)


class DashboardOperationEntity(Model):
    """Durable, idempotent collaboration operation.

    The operation log stores only schema patches. Presence and short-lived
    connection tickets are deliberately ephemeral and never written here.
    """

    __tablename__ = "dbgpt_dashboard_operation"
    __table_args__ = (
        UniqueConstraint(
            "dashboard_id", "operation_id", name="uk_dashboard_operation_id"
        ),
        UniqueConstraint(
            "dashboard_id",
            "applied_revision",
            name="uk_dashboard_operation_revision",
        ),
    )

    id = Column(
        Integer().with_variant(BigInteger(), "mysql"),
        primary_key=True,
        autoincrement=True,
    )
    dashboard_id = Column(String(64), nullable=False, index=True)
    operation_id = Column(String(64), nullable=False)
    client_id = Column(String(128), nullable=False, index=True)
    actor_id = Column(String(255), nullable=False, index=True)
    base_revision = Column(Integer, nullable=False)
    applied_revision = Column(Integer, nullable=False)
    patch_json = Column(_json_text_type(), nullable=False)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now, index=True)


class DashboardAnnotationEntity(Model):
    """Durable selection-aware comment and its validated Agent proposal."""

    __tablename__ = "dbgpt_dashboard_annotation"

    id = Column(String(64), primary_key=True)
    dashboard_id = Column(String(64), nullable=False, index=True)
    actor_id = Column(String(255), nullable=False, index=True)
    conversation_id = Column(String(255), nullable=True, index=True)
    source_turn_id = Column(String(64), nullable=True, index=True)
    base_revision = Column(Integer, nullable=False, index=True)
    target_json = Column(_json_text_type(), nullable=False)
    prompt = Column(_json_text_type(), nullable=False)
    intent = Column(
        String(32), nullable=False, default="modify", server_default="modify"
    )
    status = Column(String(32), nullable=False, default="pending", index=True)
    proposal_json = Column(_json_text_type(), nullable=True)
    resolved_at = Column(DateTime, nullable=True, index=True)
    gmt_created = Column(DateTime, nullable=False, default=datetime.now, index=True)
    gmt_modified = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )


def _copy_dashboard(row: DashboardEntity) -> DashboardEntity:
    return DashboardEntity(
        id=row.id,
        owner_id=row.owner_id,
        conversation_id=row.conversation_id,
        source_turn_id=row.source_turn_id,
        origin=row.origin,
        asset_state=row.asset_state,
        saved_at=row.saved_at,
        title=row.title,
        description=row.description,
        data_source_id=row.data_source_id,
        schema_json=row.schema_json,
        current_revision=row.current_revision,
        status=row.status,
        public_slug=row.public_slug,
        gmt_created=row.gmt_created,
        gmt_modified=row.gmt_modified,
    )


def _copy_edit_version(
    row: DashboardEditVersionEntity,
) -> DashboardEditVersionEntity:
    return DashboardEditVersionEntity(
        id=row.id,
        dashboard_id=row.dashboard_id,
        revision=row.revision,
        schema_json=row.schema_json,
        source=row.source,
        actor_id=row.actor_id,
        operation_id=row.operation_id,
        gmt_created=row.gmt_created,
    )


def _copy_revision(row: DashboardRevisionEntity) -> DashboardRevisionEntity:
    return DashboardRevisionEntity(
        id=row.id,
        dashboard_id=row.dashboard_id,
        revision=row.revision,
        schema_json=row.schema_json,
        snapshot_json=row.snapshot_json,
        validation_json=row.validation_json,
        share_token_hash=row.share_token_hash,
        gmt_published=row.gmt_published,
    )


def _copy_share(row: DashboardShareEntity) -> DashboardShareEntity:
    return DashboardShareEntity(
        id=row.id,
        dashboard_id=row.dashboard_id,
        revision=row.revision,
        token_hash=row.token_hash,
        created_by=row.created_by,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        gmt_created=row.gmt_created,
    )


def _copy_member(row: DashboardMemberEntity) -> DashboardMemberEntity:
    return DashboardMemberEntity(
        id=row.id,
        dashboard_id=row.dashboard_id,
        principal_id=row.principal_id,
        role=row.role,
        created_by=row.created_by,
        gmt_created=row.gmt_created,
        gmt_modified=row.gmt_modified,
    )


def _copy_audit(row: DashboardAuditEntity) -> DashboardAuditEntity:
    return DashboardAuditEntity(
        id=row.id,
        dashboard_id=row.dashboard_id,
        actor_id=row.actor_id,
        action=row.action,
        target_type=row.target_type,
        target_id=row.target_id,
        details_json=row.details_json,
        request_id=row.request_id,
        gmt_created=row.gmt_created,
    )


def _copy_operation(row: DashboardOperationEntity) -> DashboardOperationEntity:
    return DashboardOperationEntity(
        id=row.id,
        dashboard_id=row.dashboard_id,
        operation_id=row.operation_id,
        client_id=row.client_id,
        actor_id=row.actor_id,
        base_revision=row.base_revision,
        applied_revision=row.applied_revision,
        patch_json=row.patch_json,
        gmt_created=row.gmt_created,
    )


def _copy_annotation(row: DashboardAnnotationEntity) -> DashboardAnnotationEntity:
    return DashboardAnnotationEntity(
        id=row.id,
        dashboard_id=row.dashboard_id,
        actor_id=row.actor_id,
        conversation_id=row.conversation_id,
        source_turn_id=row.source_turn_id,
        base_revision=row.base_revision,
        target_json=row.target_json,
        prompt=row.prompt,
        intent=row.intent or "modify",
        status=row.status,
        proposal_json=row.proposal_json,
        resolved_at=row.resolved_at,
        gmt_created=row.gmt_created,
        gmt_modified=row.gmt_modified,
    )


class DashboardDao(BaseDao):
    def remember_share_token(self, token):
        from .share_vault import remember_share_token

        remember_share_token(self, token)

    @staticmethod
    def _prune_versions(session, dashboard_id: str) -> None:
        """Retain 20 snapshots in total, including current edit and latest publish.

        Revision numbers never reset. Call under the dashboard write lock.
        Revocable links to expired snapshots are removed with their revision.
        """
        session.flush()
        edits = (
            session.query(
                DashboardEditVersionEntity.id, DashboardEditVersionEntity.gmt_created
            )
            .filter_by(dashboard_id=dashboard_id)
            .order_by(DashboardEditVersionEntity.revision.desc())
            .all()
        )
        pubs = (
            session.query(
                DashboardRevisionEntity.id, DashboardRevisionEntity.gmt_published
            )
            .filter_by(dashboard_id=dashboard_id)
            .order_by(DashboardRevisionEntity.revision.desc())
            .all()
        )
        required = [
            (kind, rows[0][0])
            for kind, rows in [("edit", edits), ("pub", pubs)]
            if rows
        ]
        recent = sorted(
            [
                (when, kind, key)
                for kind, rows in [("edit", edits), ("pub", pubs)]
                for key, when in rows
            ],
            reverse=True,
        )
        keep = set(required)
        for _, kind, key in recent:
            if len(keep) >= 20:
                break
            keep.add((kind, key))
        for kind, model in [
            ("edit", DashboardEditVersionEntity),
            ("pub", DashboardRevisionEntity),
        ]:
            ids = [key for category, key in keep if category == kind]
            session.query(model).filter(
                model.dashboard_id == dashboard_id, model.id.notin_(ids)
            ).delete(synchronize_session=False)
        revisions = session.query(DashboardRevisionEntity.revision).filter_by(
            dashboard_id=dashboard_id
        )
        session.query(DashboardShareEntity).filter(
            DashboardShareEntity.dashboard_id == dashboard_id,
            DashboardShareEntity.revision.notin_(revisions),
        ).delete(synchronize_session=False)

    def prune_versions(self, dashboard_id: str) -> None:
        with self.session() as session:
            session.query(DashboardEntity).filter_by(
                id=dashboard_id
            ).with_for_update().one()
            self._prune_versions(session, dashboard_id)

    def ensure_assistant_conversation(self, dashboard_id: str, actor_id: str) -> str:
        # The agent conversation store is initialized lazily on its first message.
        # Attaching a task changes provenance only, never the published schema.
        import uuid

        with self.session() as session:
            row = (
                session.query(DashboardEntity)
                .filter_by(id=dashboard_id)
                .with_for_update()
                .one()
            )
            if not row.conversation_id:
                row.conversation_id = str(uuid.uuid4())
                payload = json.loads(row.schema_json)
                payload.setdefault("metadata", {})["conversation_id"] = (
                    row.conversation_id
                )
                row.schema_json = json.dumps(payload, ensure_ascii=False)
                session.flush()
            return row.conversation_id

    @staticmethod
    def _append_edit_version(
        session,
        dashboard: DashboardEntity,
        *,
        source: str,
        actor_id: Optional[str] = None,
        operation_id: Optional[str] = None,
    ) -> None:
        session.add(
            DashboardEditVersionEntity(
                dashboard_id=dashboard.id,
                revision=dashboard.current_revision,
                schema_json=dashboard.schema_json,
                source=source,
                actor_id=actor_id or dashboard.owner_id,
                operation_id=operation_id,
                gmt_created=dashboard.gmt_modified or datetime.now(),
            )
        )

        DashboardDao._prune_versions(session, dashboard.id)

    def create_dashboard(
        self, entity: DashboardEntity, *, ensure_owner_member: bool = False
    ) -> DashboardEntity:
        with self.session() as session:
            session.add(entity)
            if ensure_owner_member:
                session.add(
                    DashboardMemberEntity(
                        dashboard_id=entity.id,
                        principal_id=entity.owner_id,
                        role="owner",
                        created_by=entity.owner_id,
                    )
                )
            initial_source = {
                "task": "agent_create",
                "template": "template_create",
            }.get(entity.origin or "", "create")
            self._append_edit_version(
                session,
                entity,
                source=initial_source,
                actor_id=entity.owner_id,
            )
            session.flush()
            session.refresh(entity)
            return _copy_dashboard(entity)

    def get_dashboard(
        self, dashboard_id: str, owner_id: Optional[str] = None
    ) -> Optional[DashboardEntity]:
        with self.session(commit=False) as session:
            query = session.query(DashboardEntity).filter_by(id=dashboard_id)
            if owner_id is not None:
                query = query.filter_by(owner_id=owner_id)
            row = query.first()
            return _copy_dashboard(row) if row else None

    def get_dashboard_by_id(self, dashboard_id: str) -> Optional[DashboardEntity]:
        return self.get_dashboard(dashboard_id)

    def get_dashboard_by_public_slug(
        self, public_slug: str
    ) -> Optional[DashboardEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardEntity)
                .filter_by(public_slug=public_slug)
                .first()
            )
            return _copy_dashboard(row) if row else None

    def list_dashboards(
        self,
        owner_id: str,
        *,
        conversation_id: Optional[str] = None,
        origin: Optional[str] = None,
        exclude_origin: Optional[str] = None,
        asset_state: Optional[str] = None,
        status: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[DashboardEntity]:
        with self.session(commit=False) as session:
            query = session.query(DashboardEntity).filter_by(owner_id=owner_id)
            if conversation_id is not None:
                query = query.filter(DashboardEntity.conversation_id == conversation_id)
            if origin is not None:
                query = query.filter(DashboardEntity.origin == origin)
            if exclude_origin is not None:
                query = query.filter(DashboardEntity.origin != exclude_origin)
            if asset_state is not None:
                query = query.filter(DashboardEntity.asset_state == asset_state)
            if status is not None:
                query = query.filter(DashboardEntity.status == status)
            elif not include_archived:
                query = query.filter(DashboardEntity.status != "archived")
            rows = query.order_by(DashboardEntity.gmt_modified.desc()).all()
            return [_copy_dashboard(row) for row in rows]

    def list_dashboard_page(
        self,
        owner_id: str,
        *,
        folder_id: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[str] = None,
        conversation_id: Optional[str] = None,
        origin: Optional[str] = None,
        exclude_origin: Optional[str] = None,
        asset_state: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 24,
        offset: int = 0,
    ) -> Tuple[List[DashboardEntity], int]:
        with self.session(commit=False) as session:
            query = session.query(DashboardEntity).filter_by(owner_id=owner_id)
            from .folders import folder_scope

            query = folder_scope(query, session, owner_id, folder_id, DashboardEntity)
            if search:
                pattern = f"%{search.strip().casefold()}%"
                query = query.filter(
                    or_(
                        func.lower(DashboardEntity.title).like(pattern),
                        func.lower(DashboardEntity.description).like(pattern),
                    )
                )
            if status:
                query = query.filter(DashboardEntity.status == status)
            elif not include_archived:
                query = query.filter(DashboardEntity.status != "archived")
            if conversation_id is not None:
                query = query.filter(DashboardEntity.conversation_id == conversation_id)
            if origin is not None:
                query = query.filter(DashboardEntity.origin == origin)
            if exclude_origin is not None:
                query = query.filter(DashboardEntity.origin != exclude_origin)
            if asset_state is not None:
                query = query.filter(DashboardEntity.asset_state == asset_state)
            total = int(query.with_entities(func.count()).scalar() or 0)
            rows = (
                query.order_by(DashboardEntity.gmt_modified.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [_copy_dashboard(row) for row in rows], total

    def update_dashboard_status(
        self,
        dashboard_id: str,
        owner_id: Optional[str],
        expected_revision: int,
        *,
        status: str,
        schema_json: str,
        version_source: str = "status_change",
        version_actor_id: Optional[str] = None,
        version_operation_id: Optional[str] = None,
    ) -> DashboardEntity:
        with self.session() as session:
            query = session.query(DashboardEntity).filter_by(id=dashboard_id)
            if owner_id is not None:
                query = query.filter_by(owner_id=owner_id)
            row = query.with_for_update().first()
            if row is None:
                raise DashboardNotFoundError(dashboard_id)
            if row.current_revision != expected_revision:
                raise DashboardConflictError(
                    f"Dashboard revision changed from {expected_revision} "
                    f"to {row.current_revision}."
                )
            row.status = status
            row.schema_json = schema_json
            row.current_revision += 1
            row.gmt_modified = datetime.now()
            self._append_edit_version(
                session,
                row,
                source=version_source,
                actor_id=version_actor_id,
                operation_id=version_operation_id,
            )
            session.flush()
            return _copy_dashboard(row)

    def update_dashboard(
        self,
        dashboard_id: str,
        owner_id: Optional[str],
        expected_revision: int,
        *,
        title: str,
        description: str,
        data_source_id: str,
        schema_json: str,
        promote_to_asset: bool = True,
        version_source: str = "manual_edit",
        version_actor_id: Optional[str] = None,
        version_operation_id: Optional[str] = None,
    ) -> DashboardEntity:
        with self.session() as session:
            query = session.query(DashboardEntity).filter_by(id=dashboard_id)
            if owner_id is not None:
                query = query.filter_by(owner_id=owner_id)
            row = query.with_for_update().first()
            if row is None:
                raise DashboardNotFoundError(dashboard_id)
            if row.current_revision != expected_revision:
                raise DashboardConflictError(
                    f"Dashboard revision changed from {expected_revision} "
                    f"to {row.current_revision}."
                )
            row.title = title
            row.description = description
            row.data_source_id = data_source_id
            row.schema_json = schema_json
            row.current_revision += 1
            row.status = "draft"
            if promote_to_asset:
                row.asset_state = "saved"
                row.saved_at = row.saved_at or datetime.now()
            row.gmt_modified = datetime.now()
            self._append_edit_version(
                session,
                row,
                source=version_source,
                actor_id=version_actor_id,
                operation_id=version_operation_id,
            )
            session.flush()
            return _copy_dashboard(row)

    def apply_operation(
        self,
        dashboard_id: str,
        expected_revision: int,
        *,
        operation_id: str,
        client_id: str,
        actor_id: str,
        patch_json: str,
        transform: Callable[[str], Tuple[str, str, str, str]],
        promote_to_asset: bool = True,
        version_source: Optional[str] = None,
    ) -> Tuple[DashboardEntity, DashboardOperationEntity, bool]:
        """Atomically validate/transform a draft and append its operation log.

        ``transform`` receives the current schema JSON while the dashboard row is
        locked and returns ``(schema_json, title, description, data_source_id)``.
        A repeated operation id is returned as a replay without mutating state.
        """

        with self.session() as session:
            existing = (
                session.query(DashboardOperationEntity)
                .filter_by(dashboard_id=dashboard_id, operation_id=operation_id)
                .first()
            )
            if existing is not None:
                dashboard = (
                    session.query(DashboardEntity).filter_by(id=dashboard_id).first()
                )
                if dashboard is None:  # pragma: no cover - referential invariant
                    raise DashboardNotFoundError(dashboard_id)
                return _copy_dashboard(dashboard), _copy_operation(existing), True

            dashboard = (
                session.query(DashboardEntity)
                .filter_by(id=dashboard_id)
                .with_for_update()
                .first()
            )
            if dashboard is None:
                raise DashboardNotFoundError(dashboard_id)
            # A concurrent request may have committed the same id while this
            # transaction waited for the dashboard lock. Recheck after locking so
            # retry-safe idempotency wins over a stale-revision response.
            existing = (
                session.query(DashboardOperationEntity)
                .filter_by(dashboard_id=dashboard_id, operation_id=operation_id)
                .first()
            )
            if existing is not None:
                return _copy_dashboard(dashboard), _copy_operation(existing), True
            if dashboard.current_revision != expected_revision:
                raise DashboardConflictError(
                    f"Dashboard revision changed from {expected_revision} "
                    f"to {dashboard.current_revision}."
                )

            schema_json, title, description, data_source_id = transform(
                dashboard.schema_json
            )
            applied_revision = dashboard.current_revision + 1
            dashboard.schema_json = schema_json
            dashboard.title = title
            dashboard.description = description
            dashboard.data_source_id = data_source_id
            dashboard.current_revision = applied_revision
            dashboard.status = "draft"
            if promote_to_asset:
                dashboard.asset_state = "saved"
                dashboard.saved_at = dashboard.saved_at or datetime.now()
            dashboard.gmt_modified = datetime.now()
            operation = DashboardOperationEntity(
                dashboard_id=dashboard_id,
                operation_id=operation_id,
                client_id=client_id,
                actor_id=actor_id,
                base_revision=expected_revision,
                applied_revision=applied_revision,
                patch_json=patch_json,
                gmt_created=datetime.now(),
            )
            session.add(operation)
            self._append_edit_version(
                session,
                dashboard,
                source=(
                    version_source
                    or ("ai_edit" if client_id == "dashboard-agent" else "manual_edit")
                ),
                actor_id=actor_id,
                operation_id=operation_id,
            )
            session.flush()
            session.refresh(operation)
            return _copy_dashboard(dashboard), _copy_operation(operation), False

    def get_edit_version(
        self, dashboard_id: str, revision: int
    ) -> Optional[DashboardEditVersionEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardEditVersionEntity)
                .filter_by(dashboard_id=dashboard_id, revision=revision)
                .one_or_none()
            )
            return _copy_edit_version(row) if row else None

    def list_edit_versions(
        self,
        dashboard_id: str,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> List[DashboardEditVersionEntity]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardEditVersionEntity)
                .filter_by(dashboard_id=dashboard_id)
                .order_by(DashboardEditVersionEntity.revision.desc())
                .offset(min(max(offset, 0), 20))
                .limit(min(max(limit, 0), max(0, 20 - offset)))
                .all()
            )
            return [_copy_edit_version(row) for row in rows]

    def get_operation(
        self, dashboard_id: str, operation_id: str
    ) -> Optional[DashboardOperationEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardOperationEntity)
                .filter_by(dashboard_id=dashboard_id, operation_id=operation_id)
                .first()
            )
            return _copy_operation(row) if row else None

    def list_operations(
        self,
        dashboard_id: str,
        *,
        after_revision: int = 0,
        limit: int = 200,
    ) -> List[DashboardOperationEntity]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardOperationEntity)
                .filter(
                    DashboardOperationEntity.dashboard_id == dashboard_id,
                    DashboardOperationEntity.applied_revision > after_revision,
                )
                .order_by(DashboardOperationEntity.applied_revision.asc())
                .limit(limit)
                .all()
            )
            return [_copy_operation(row) for row in rows]

    def create_annotation(
        self, entity: DashboardAnnotationEntity
    ) -> DashboardAnnotationEntity:
        with self.session() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _copy_annotation(entity)

    def get_annotation(self, annotation_id: str) -> Optional[DashboardAnnotationEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardAnnotationEntity)
                .filter_by(id=annotation_id)
                .one_or_none()
            )
            return _copy_annotation(row) if row else None

    def list_annotations(
        self, dashboard_id: str, *, limit: int = 100, offset: int = 0
    ) -> List[DashboardAnnotationEntity]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardAnnotationEntity)
                .filter_by(dashboard_id=dashboard_id)
                .order_by(DashboardAnnotationEntity.gmt_created.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [_copy_annotation(row) for row in rows]

    def update_annotation(
        self,
        annotation_id: str,
        *,
        status: str,
        proposal_json: Optional[str] = None,
        resolved_at: Optional[datetime] = None,
    ) -> DashboardAnnotationEntity:
        with self.session() as session:
            row = (
                session.query(DashboardAnnotationEntity)
                .filter_by(id=annotation_id)
                .one_or_none()
            )
            if row is None:
                raise DashboardNotFoundError(annotation_id)
            row.status = status
            if proposal_json is not None:
                row.proposal_json = proposal_json
            row.resolved_at = resolved_at
            row.gmt_modified = datetime.now()
            session.flush()
            session.refresh(row)
            return _copy_annotation(row)

    def publish_dashboard(
        self,
        dashboard_id: str,
        owner_id: Optional[str],
        expected_revision: int,
        *,
        schema_json: str,
        snapshot_json: str,
        validation_json: str,
        share_token_hash: str,
        public_slug: Optional[str] = None,
        share_created_by: Optional[str] = None,
        share_expires_at: Optional[datetime] = None,
    ) -> Tuple[DashboardRevisionEntity, DashboardEntity]:
        with self.session() as session:
            query = session.query(DashboardEntity).filter_by(id=dashboard_id)
            if owner_id is not None:
                query = query.filter_by(owner_id=owner_id)
            dashboard = query.with_for_update().first()
            if dashboard is None:
                raise DashboardNotFoundError(dashboard_id)
            if dashboard.current_revision != expected_revision:
                raise DashboardConflictError(
                    f"Dashboard revision changed from {expected_revision} "
                    f"to {dashboard.current_revision}."
                )
            latest = (
                session.query(func.max(DashboardRevisionEntity.revision))
                .filter_by(dashboard_id=dashboard_id)
                .scalar()
                or 0
            )
            revision = DashboardRevisionEntity(
                dashboard_id=dashboard_id,
                revision=latest + 1,
                schema_json=schema_json,
                snapshot_json=snapshot_json,
                validation_json=validation_json,
                share_token_hash=share_token_hash,
                gmt_published=datetime.now(),
            )
            session.add(revision)
            session.add(
                DashboardShareEntity(
                    dashboard_id=dashboard_id,
                    revision=revision.revision,
                    token_hash=share_token_hash,
                    created_by=share_created_by or dashboard.owner_id,
                    expires_at=share_expires_at,
                    gmt_created=revision.gmt_published,
                )
            )
            dashboard.status = "published"
            if dashboard.public_slug is None and public_slug:
                dashboard.public_slug = public_slug
            dashboard.asset_state = "saved"
            dashboard.saved_at = dashboard.saved_at or datetime.now()
            dashboard.gmt_modified = datetime.now()
            session.flush()

            self._prune_versions(session, dashboard_id)
            session.refresh(revision)
            return _copy_revision(revision), _copy_dashboard(dashboard)

    def get_published_by_token_hash(
        self, token_hash: str
    ) -> Optional[DashboardRevisionEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardRevisionEntity)
                .filter_by(share_token_hash=token_hash)
                .first()
            )
            return _copy_revision(row) if row else None

    def get_published_revision(
        self, dashboard_id: str, revision: int
    ) -> Optional[DashboardRevisionEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardRevisionEntity)
                .filter_by(dashboard_id=dashboard_id, revision=revision)
                .first()
            )
            return _copy_revision(row) if row else None

    def list_published_revisions(
        self, dashboard_id: str
    ) -> List[DashboardRevisionEntity]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardRevisionEntity)
                .filter_by(dashboard_id=dashboard_id)
                .order_by(DashboardRevisionEntity.revision.desc())
                .limit(20)
                .all()
            )
            return [_copy_revision(row) for row in rows]

    def get_latest_published_revision(
        self, dashboard_id: str
    ) -> Optional[DashboardRevisionEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardRevisionEntity)
                .filter_by(dashboard_id=dashboard_id)
                .order_by(DashboardRevisionEntity.revision.desc())
                .first()
            )
            return _copy_revision(row) if row else None

    def get_active_published_by_token_hash(
        self, token_hash: str, *, now: Optional[datetime] = None
    ) -> Optional[DashboardRevisionEntity]:
        """Resolve a live share without exposing its token or executing SQL."""

        now = now or datetime.now()
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardRevisionEntity)
                .join(
                    DashboardShareEntity,
                    (
                        DashboardShareEntity.dashboard_id
                        == DashboardRevisionEntity.dashboard_id
                    )
                    & (
                        DashboardShareEntity.revision
                        == DashboardRevisionEntity.revision
                    ),
                )
                .filter(
                    DashboardShareEntity.token_hash == token_hash,
                    DashboardShareEntity.revoked_at.is_(None),
                    (DashboardShareEntity.expires_at.is_(None))
                    | (DashboardShareEntity.expires_at > now),
                )
                .first()
            )
            return _copy_revision(row) if row else None

    def list_shares(self, dashboard_id: str) -> List[DashboardShareEntity]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardShareEntity)
                .filter_by(dashboard_id=dashboard_id)
                .order_by(DashboardShareEntity.gmt_created.desc())
                .limit(20)
                .all()
            )
            return [_copy_share(row) for row in rows]

    def rotate_share(
        self,
        dashboard_id: str,
        revision: int,
        token_hash: str,
        *,
        created_by: str,
        expires_at: Optional[datetime] = None,
    ) -> DashboardShareEntity:
        now = datetime.now()
        with self.session() as session:
            published = (
                session.query(DashboardRevisionEntity)
                .filter_by(dashboard_id=dashboard_id, revision=revision)
                .with_for_update()
                .first()
            )
            if published is None:
                raise DashboardNotFoundError(
                    f"Published revision {dashboard_id}/{revision}"
                )
            (
                session.query(DashboardShareEntity)
                .filter_by(
                    dashboard_id=dashboard_id, revision=revision, revoked_at=None
                )
                .update({"revoked_at": now}, synchronize_session=False)
            )
            share = DashboardShareEntity(
                dashboard_id=dashboard_id,
                revision=revision,
                token_hash=token_hash,
                created_by=created_by,
                expires_at=expires_at,
                gmt_created=now,
            )
            session.add(share)
            session.flush()
            session.refresh(share)
            return _copy_share(share)

    def revoke_shares(self, dashboard_id: str, revision: int) -> int:
        with self.session() as session:
            return int(
                session.query(DashboardShareEntity)
                .filter_by(
                    dashboard_id=dashboard_id, revision=revision, revoked_at=None
                )
                .update({"revoked_at": datetime.now()}, synchronize_session=False)
            )


class DashboardAccessDao(BaseDao):
    """Persistence boundary for members and accessible-dashboard lookup."""

    def ensure_owner(self, dashboard_id: str, owner_id: str) -> DashboardMemberEntity:
        with self.session() as session:
            row = (
                session.query(DashboardMemberEntity)
                .filter_by(dashboard_id=dashboard_id, principal_id=owner_id)
                .with_for_update()
                .first()
            )
            if row is None:
                row = DashboardMemberEntity(
                    dashboard_id=dashboard_id,
                    principal_id=owner_id,
                    role="owner",
                    created_by=owner_id,
                )
                session.add(row)
            else:
                row.role = "owner"
                row.gmt_modified = datetime.now()
            session.flush()
            session.refresh(row)
            return _copy_member(row)

    def get_member(
        self, dashboard_id: str, principal_id: str
    ) -> Optional[DashboardMemberEntity]:
        with self.session(commit=False) as session:
            row = (
                session.query(DashboardMemberEntity)
                .filter_by(dashboard_id=dashboard_id, principal_id=principal_id)
                .first()
            )
            return _copy_member(row) if row else None

    def list_accessible_dashboards(
        self,
        actor_id: str,
        *,
        folder_id: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[str] = None,
        conversation_id: Optional[str] = None,
        origin: Optional[str] = None,
        exclude_origin: Optional[str] = None,
        asset_state: Optional[str] = None,
        include_archived: bool = False,
        limit: int = 24,
        offset: int = 0,
    ) -> Tuple[List[DashboardEntity], int]:
        """Return one page with two fixed queries instead of per-row lookups."""

        with self.session(commit=False) as session:
            accessible_ids = (
                session.query(DashboardEntity.id.label("dashboard_id"))
                .outerjoin(
                    DashboardMemberEntity,
                    DashboardMemberEntity.dashboard_id == DashboardEntity.id,
                )
                .filter(
                    or_(
                        DashboardEntity.owner_id == actor_id,
                        DashboardMemberEntity.principal_id == actor_id,
                    )
                )
            )
            from .folders import folder_scope

            accessible_ids = folder_scope(
                accessible_ids, session, actor_id, folder_id, DashboardEntity
            )
            if search:
                pattern = f"%{search.strip().casefold()}%"
                accessible_ids = accessible_ids.filter(
                    or_(
                        func.lower(DashboardEntity.title).like(pattern),
                        func.lower(DashboardEntity.description).like(pattern),
                    )
                )
            if status:
                accessible_ids = accessible_ids.filter(DashboardEntity.status == status)
            elif not include_archived:
                accessible_ids = accessible_ids.filter(
                    DashboardEntity.status != "archived"
                )
            if conversation_id is not None:
                accessible_ids = accessible_ids.filter(
                    DashboardEntity.conversation_id == conversation_id
                )
            if origin is not None:
                accessible_ids = accessible_ids.filter(DashboardEntity.origin == origin)
            if exclude_origin is not None:
                accessible_ids = accessible_ids.filter(
                    DashboardEntity.origin != exclude_origin
                )
            if asset_state is not None:
                accessible_ids = accessible_ids.filter(
                    DashboardEntity.asset_state == asset_state
                )
            accessible_ids = accessible_ids.distinct().subquery()
            total = int(
                session.query(func.count()).select_from(accessible_ids).scalar() or 0
            )
            rows = (
                session.query(DashboardEntity)
                .join(
                    accessible_ids,
                    accessible_ids.c.dashboard_id == DashboardEntity.id,
                )
                .order_by(DashboardEntity.gmt_modified.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [_copy_dashboard(row) for row in rows], total

    def list_members(self, dashboard_id: str) -> List[DashboardMemberEntity]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardMemberEntity)
                .filter_by(dashboard_id=dashboard_id)
                .order_by(
                    DashboardMemberEntity.role, DashboardMemberEntity.principal_id
                )
                .all()
            )
            return [_copy_member(row) for row in rows]

    def upsert_member(
        self,
        dashboard_id: str,
        principal_id: str,
        role: str,
        created_by: str,
    ) -> DashboardMemberEntity:
        with self.session() as session:
            row = (
                session.query(DashboardMemberEntity)
                .filter_by(dashboard_id=dashboard_id, principal_id=principal_id)
                .with_for_update()
                .first()
            )
            if row is None:
                row = DashboardMemberEntity(
                    dashboard_id=dashboard_id,
                    principal_id=principal_id,
                    role=role,
                    created_by=created_by,
                )
                session.add(row)
            else:
                row.role = role
                row.gmt_modified = datetime.now()
            session.flush()
            session.refresh(row)
            return _copy_member(row)

    def delete_member(self, dashboard_id: str, principal_id: str) -> bool:
        with self.session() as session:
            count = (
                session.query(DashboardMemberEntity)
                .filter_by(dashboard_id=dashboard_id, principal_id=principal_id)
                .delete(synchronize_session=False)
            )
            return bool(count)

    def list_accessible_dashboard_ids(self, principal_id: str) -> List[str]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardMemberEntity.dashboard_id)
                .filter_by(principal_id=principal_id)
                .all()
            )
            return [str(row[0]) for row in rows]


class DashboardAuditDao(BaseDao):
    def append(self, entity: DashboardAuditEntity) -> DashboardAuditEntity:
        with self.session() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
            return _copy_audit(entity)

    def list_for_dashboard(
        self, dashboard_id: str, *, limit: int = 100, offset: int = 0
    ) -> List[DashboardAuditEntity]:
        with self.session(commit=False) as session:
            rows = (
                session.query(DashboardAuditEntity)
                .filter_by(dashboard_id=dashboard_id)
                .order_by(DashboardAuditEntity.gmt_created.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [_copy_audit(row) for row in rows]
