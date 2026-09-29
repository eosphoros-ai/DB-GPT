"""Application service for dashboard drafts, queries, and immutable publishing."""

import hashlib
import json
import re
import secrets
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from .access import DashboardAuthorizationService
from .generation_budget import check_generation_deadline
from .lineage import enrich_schema_lineage
from .models import (
    DashboardConflictError,
    DashboardDao,
    DashboardEntity,
    DashboardNotFoundError,
)
from .publication import DashboardPublicationError, DashboardPublicationService
from .query_executor import DashboardQueryExecutor
from .schemas import (
    DashboardAction,
    DashboardArtifactBundle,
    DashboardArtifactFile,
    DashboardAssetState,
    DashboardAuditRecord,
    DashboardCopyRequest,
    DashboardCreateRequest,
    DashboardEditVersionDetail,
    DashboardEditVersionRecord,
    DashboardListItem,
    DashboardListPage,
    DashboardMemberRecord,
    DashboardOrigin,
    DashboardPermissionRecord,
    DashboardPublishResponse,
    DashboardRecord,
    DashboardRevisionRecord,
    DashboardRole,
    DashboardSchemaV1,
    DashboardShareRecord,
    DashboardSnapshot,
    DashboardStatus,
    DashboardValidationResult,
    PublicDashboardFilterResponse,
    PublicDashboardSnapshot,
    ValidationIssue,
    WidgetQueryResult,
    model_dump_compat,
    model_validate_compat,
)

MAX_PUBLISHED_SNAPSHOT_BYTES = 10 * 1024 * 1024


class DashboardSchemaValidationError(ValueError):
    def __init__(self, issues: List[ValidationIssue]):
        super().__init__("Dashboard schema validation failed.")
        self.issues = issues


class DashboardPublishValidationError(ValueError):
    def __init__(self, result: DashboardValidationResult):
        super().__init__("Dashboard cannot be published until validation passes.")
        self.result = result


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), default=_json_default
    )


def _model_copy(model, *, deep: bool = False):
    if hasattr(model, "model_copy"):
        return model.model_copy(deep=deep)
    return model.copy(deep=deep)


class DashboardService:
    """A deterministic backend boundary; model-generated content is never trusted."""

    def __init__(
        self,
        dao: Optional[DashboardDao] = None,
        connector_resolver: Optional[Callable[[str], Any]] = None,
        authorization_service: Optional[DashboardAuthorizationService] = None,
        query_executor: Optional[DashboardQueryExecutor] = None,
        publication_service: Optional[DashboardPublicationService] = None,
    ) -> None:
        use_default_authorization = dao is None and authorization_service is None
        self.dao = dao or DashboardDao()
        self.query_executor = query_executor or DashboardQueryExecutor(
            connector_resolver=connector_resolver
        )
        self.publication_service = publication_service or DashboardPublicationService()
        self.authorization = authorization_service
        if use_default_authorization:
            self.authorization = DashboardAuthorizationService(dashboard_dao=self.dao)

    @staticmethod
    def _owner(owner_id: Optional[str]) -> str:
        return owner_id or "001"

    @staticmethod
    def _serialize_schema(schema: DashboardSchemaV1) -> str:
        return _json_dumps(model_dump_compat(schema))

    @staticmethod
    def _parse_schema(payload: str) -> DashboardSchemaV1:
        return model_validate_compat(DashboardSchemaV1, json.loads(payload))

    def _to_record(self, entity: DashboardEntity) -> DashboardRecord:
        return DashboardRecord(
            id=entity.id,
            owner_id=entity.owner_id,
            conversation_id=entity.conversation_id,
            source_turn_id=entity.source_turn_id,
            origin=entity.origin or DashboardOrigin.MANUAL,
            asset_state=entity.asset_state or DashboardAssetState.SAVED,
            saved_at=entity.saved_at,
            current_revision=entity.current_revision,
            status=entity.status,
            schema=self._parse_schema(entity.schema_json),
            created_at=entity.gmt_created,
            updated_at=entity.gmt_modified,
        )

    def _to_list_item(self, entity: DashboardEntity) -> DashboardListItem:
        schema = self._parse_schema(entity.schema_json)
        return DashboardListItem(
            id=entity.id,
            title=schema.dashboard.title,
            description=schema.dashboard.description,
            data_source_id=schema.dashboard.data_source_id,
            conversation_id=entity.conversation_id,
            source_turn_id=entity.source_turn_id,
            origin=entity.origin or DashboardOrigin.MANUAL,
            asset_state=entity.asset_state or DashboardAssetState.SAVED,
            saved_at=entity.saved_at,
            current_revision=entity.current_revision,
            status=entity.status,
            updated_at=entity.gmt_modified,
        )

    def _authorized_entity(
        self,
        dashboard_id: str,
        actor_id: Optional[str],
        action: DashboardAction,
        *,
        data_source_ids: Optional[List[str]] = None,
    ) -> DashboardEntity:
        actor = self._owner(actor_id)
        if self.authorization is not None:
            return self.authorization.require(
                dashboard_id,
                actor,
                action,
                data_source_ids=data_source_ids,
            )
        entity = self.dao.get_dashboard(dashboard_id, actor)
        if entity is None:
            raise DashboardNotFoundError(dashboard_id)
        return entity

    @staticmethod
    def _schema_data_source_ids(schema: DashboardSchemaV1) -> List[str]:
        source_ids = {schema.dashboard.data_source_id}
        for widget in schema.widgets:
            federation = widget.query.federation
            if federation is None:
                source_ids.add(widget.query.data_source_id)
            else:
                source_ids.update(
                    source.data_source_id for source in federation.sources
                )
        return sorted(source_id for source_id in source_ids if source_id)

    def authorize_schema_sources(
        self, actor_id: Optional[str], schema: DashboardSchemaV1
    ) -> None:
        if self.authorization is not None:
            self.authorization.require_data_sources(
                self._owner(actor_id), self._schema_data_source_ids(schema)
            )

    def _audit(
        self,
        dashboard_id: str,
        actor_id: Optional[str],
        action: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        target_type: str = "dashboard",
        target_id: Optional[str] = None,
    ) -> None:
        if self.authorization is not None:
            self.authorization.audit(
                dashboard_id,
                self._owner(actor_id),
                action,
                details=details,
                target_type=target_type,
                target_id=target_id,
            )

    def record_audit(
        self,
        dashboard_id: str,
        actor_id: Optional[str],
        action: str,
        *,
        details: Optional[Dict[str, Any]] = None,
        target_type: str = "dashboard",
        target_id: Optional[str] = None,
    ) -> None:
        self._audit(
            dashboard_id,
            actor_id,
            action,
            details=details,
            target_type=target_type,
            target_id=target_id,
        )

    def create_dashboard(
        self, request: DashboardCreateRequest, owner_id: Optional[str]
    ) -> DashboardRecord:
        return self._create_dashboard(request, owner_id, allow_errored_widgets=False)

    def create_agent_dashboard(
        self, request: DashboardCreateRequest, owner_id: Optional[str]
    ) -> DashboardRecord:
        """Persist a partially successful Agent draft without executing bad SQL.

        Only widgets already carrying a server-created ``error`` marker may skip
        query validation.  This method is not exposed through the public REST API;
        preview, refresh, update, and publish continue to enforce the normal policy.
        """

        return self._create_dashboard(request, owner_id, allow_errored_widgets=True)

    def _create_dashboard(
        self,
        request: DashboardCreateRequest,
        owner_id: Optional[str],
        *,
        allow_errored_widgets: bool,
    ) -> DashboardRecord:
        schema = _model_copy(request.schema_payload, deep=True)
        now = datetime.now()
        dashboard_id = schema.dashboard.id or uuid.uuid4().hex
        schema.dashboard.id = dashboard_id
        schema.dashboard.status = DashboardStatus.DRAFT
        schema.dashboard.created_at = schema.dashboard.created_at or now
        schema.dashboard.updated_at = now
        conversation_id = request.conversation_id or schema.metadata.conversation_id
        source_turn_id = request.source_turn_id or schema.metadata.source_turn_id
        schema.metadata.conversation_id = conversation_id
        schema.metadata.source_turn_id = source_turn_id
        origin = DashboardOrigin.TASK if allow_errored_widgets else request.origin
        asset_state = (
            DashboardAssetState.GENERATED
            if allow_errored_widgets
            else request.asset_state
        )
        enrich_schema_lineage(schema)

        self.authorize_schema_sources(owner_id, schema)

        validation = self.validate_schema(
            schema,
            execute_queries=False,
            skip_errored_widgets=allow_errored_widgets,
        )
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)

        entity = DashboardEntity(
            id=dashboard_id,
            owner_id=self._owner(owner_id),
            conversation_id=conversation_id,
            source_turn_id=source_turn_id,
            origin=origin.value,
            asset_state=asset_state.value,
            saved_at=now if asset_state == DashboardAssetState.SAVED else None,
            title=schema.dashboard.title,
            description=schema.dashboard.description,
            data_source_id=schema.dashboard.data_source_id,
            schema_json=self._serialize_schema(schema),
            current_revision=1,
            status="draft",
            gmt_created=now,
            gmt_modified=now,
        )
        if self.authorization is not None:
            created = self.dao.create_dashboard(entity, ensure_owner_member=True)
        else:
            created = self.dao.create_dashboard(entity)
        self._audit(
            dashboard_id,
            owner_id,
            "dashboard.created",
            details={"agent_generated": allow_errored_widgets},
        )
        return self._to_record(created)

    def get_dashboard(
        self, dashboard_id: str, owner_id: Optional[str]
    ) -> DashboardRecord:
        entity = self._authorized_entity(dashboard_id, owner_id, DashboardAction.VIEW)
        return self._to_record(entity)

    def build_artifact_bundle(
        self, dashboard_id: str, owner_id: Optional[str]
    ) -> DashboardArtifactBundle:
        """Expose a persisted dashboard as a deterministic project tree."""

        record = self.get_dashboard(dashboard_id, owner_id)
        schema = record.schema_payload

        def safe_segment(value: str) -> str:
            segment = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
            return segment or "item"

        root = f"dashboard-{safe_segment(record.id)}"
        files: List[DashboardArtifactFile] = [
            DashboardArtifactFile(
                path="dashboard.schema.json",
                language="json",
                content=(
                    json.dumps(model_dump_compat(schema), ensure_ascii=False, indent=2)
                    + "\n"
                ),
            )
        ]
        compatibility = schema.metadata.compatibility
        stored_theme = model_dump_compat(schema.dashboard.theme)
        stored_preset = stored_theme.get("preset")
        theme_preset = (
            "clarity"
            if stored_preset in {None, "clean", "business_blue"}
            else stored_preset
        )
        theme_mode = stored_theme.get("mode") or (
            "dark" if stored_preset == "graphite" else "light"
        )
        exported_theme = {
            "preset": theme_preset,
            "mode": theme_mode,
            "overrides": {
                key: value
                for key, value in (stored_theme.get("overrides") or {}).items()
                if value is not None
            },
        }
        stored_plan = compatibility.get("dashboard_plan")
        workflow = compatibility.get("agent_dashboard_workflow")
        if stored_plan is None and isinstance(workflow, dict):
            stored_plan = workflow.get("plan")
        if stored_plan is not None:
            files.append(
                DashboardArtifactFile(
                    path="dashboard.plan.json",
                    language="json",
                    content=(
                        json.dumps(stored_plan, ensure_ascii=False, indent=2) + "\n"
                    ),
                )
            )

        for widget in schema.widgets:
            widget_name = safe_segment(widget.id)
            federation = widget.query.federation
            if federation is None:
                files.append(
                    DashboardArtifactFile(
                        path=f"queries/{widget_name}.sql",
                        language="sql",
                        content=(widget.query.sql or "-- SQL is not available") + "\n",
                    )
                )
                continue
            for source in federation.sources:
                files.append(
                    DashboardArtifactFile(
                        path=(
                            f"queries/{widget_name}/{safe_segment(source.alias)}.sql"
                        ),
                        language="sql",
                        content=source.sql + "\n",
                    )
                )

        files.append(
            DashboardArtifactFile(
                path="README.md",
                language="markdown",
                content=(
                    f"# {schema.dashboard.title}\n\n"
                    f"{schema.dashboard.description or 'DB-GPT dashboard project.'}"
                    "\n\n"
                    "This export contains the validated dashboard contract and "
                    "parameterized component SQL. It never contains executable "
                    "model-generated HTML or JavaScript.\n\n"
                    f"- Dashboard ID: `{record.id}`\n"
                    f"- Revision: `{record.current_revision}`\n"
                    f"- Data source: `{schema.dashboard.data_source_id}`\n"
                    f"- Widgets: `{len(schema.widgets)}`\n"
                    f"- Filters: `{len(schema.filters)}`\n"
                    f"- Visual theme: `{theme_preset}` / `{theme_mode}`\n\n"
                    "## Visual theme\n\n"
                    "The theme below is stored in `dashboard.schema.json` and "
                    "is applied by both the editor and the published page.\n\n"
                    "```json\n"
                    f"{json.dumps(exported_theme, ensure_ascii=False, indent=2)}\n"
                    "```\n"
                ),
            )
        )
        manifest = {
            "format": "dbgpt-dashboard-project",
            "version": 1,
            "dashboard_id": record.id,
            "revision": record.current_revision,
            "theme": exported_theme,
            "files": [item.path for item in files] + ["manifest.json"],
        }
        files.append(
            DashboardArtifactFile(
                path="manifest.json",
                language="json",
                content=json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
        )
        return DashboardArtifactBundle(
            dashboard_id=record.id,
            root=root,
            generated_at=datetime.now(),
            files=files,
        )

    def list_dashboards(
        self,
        owner_id: Optional[str],
        *,
        conversation_id: Optional[str] = None,
        origin: Optional[DashboardOrigin] = None,
        exclude_origin: Optional[DashboardOrigin] = None,
        asset_state: Optional[DashboardAssetState] = None,
        status: Optional[DashboardStatus] = None,
        include_generated: bool = False,
        include_archived: bool = False,
    ) -> List[DashboardListItem]:
        state_value = (
            None
            if include_generated
            else (asset_state or DashboardAssetState.SAVED).value
        )
        origin_value = origin.value if origin is not None else None
        excluded_origin_value = (
            exclude_origin.value if exclude_origin is not None else None
        )
        status_value = status.value if status is not None else None
        if self.authorization is not None:
            entities = self.authorization.list_accessible(
                self._owner(owner_id),
                conversation_id=conversation_id,
                origin=origin_value,
                exclude_origin=excluded_origin_value,
                asset_state=state_value,
                status=status_value,
                include_archived=include_archived,
            )
        else:
            entities = self.dao.list_dashboards(
                self._owner(owner_id),
                conversation_id=conversation_id,
                origin=origin_value,
                exclude_origin=excluded_origin_value,
                asset_state=state_value,
                status=status_value,
                include_archived=include_archived,
            )
        return [self._to_list_item(entity) for entity in entities]

    def list_dashboard_page(
        self,
        owner_id: Optional[str],
        *,
        folder_id: Optional[str] = None,
        search: Optional[str] = None,
        status: Optional[DashboardStatus] = None,
        conversation_id: Optional[str] = None,
        origin: Optional[DashboardOrigin] = None,
        exclude_origin: Optional[DashboardOrigin] = None,
        asset_state: Optional[DashboardAssetState] = None,
        include_generated: bool = False,
        include_archived: bool = False,
        limit: int = 24,
        offset: int = 0,
    ) -> DashboardListPage:
        actor = self._owner(owner_id)
        status_value = status.value if status is not None else None
        origin_value = origin.value if origin is not None else None
        excluded_origin_value = (
            exclude_origin.value if exclude_origin is not None else None
        )
        state_value = (
            None
            if include_generated
            else (asset_state or DashboardAssetState.SAVED).value
        )
        if self.authorization is not None:
            entities, total = self.authorization.list_accessible_page(
                actor,
                search=search,
                folder_id=folder_id,
                status=status_value,
                conversation_id=conversation_id,
                origin=origin_value,
                exclude_origin=excluded_origin_value,
                asset_state=state_value,
                include_archived=include_archived,
                limit=limit,
                offset=offset,
            )
        else:
            entities, total = self.dao.list_dashboard_page(
                actor,
                search=search,
                folder_id=folder_id,
                status=status_value,
                conversation_id=conversation_id,
                origin=origin_value,
                exclude_origin=excluded_origin_value,
                asset_state=state_value,
                include_archived=include_archived,
                limit=limit,
                offset=offset,
            )
        return DashboardListPage(
            items=[self._to_list_item(entity) for entity in entities],
            total=total,
            limit=limit,
            offset=offset,
        )

    def copy_dashboard(
        self,
        dashboard_id: str,
        request: DashboardCopyRequest,
        owner_id: Optional[str],
    ) -> DashboardRecord:
        source = self.get_dashboard(dashboard_id, owner_id)
        schema = _model_copy(source.schema_payload, deep=True)
        schema.dashboard.id = ""
        schema.dashboard.title = request.title or f"{schema.dashboard.title} (copy)"
        schema.dashboard.status = DashboardStatus.DRAFT
        schema.dashboard.created_at = None
        schema.dashboard.updated_at = None
        schema.metadata.conversation_id = None
        schema.metadata.source_turn_id = None
        copied = self.create_dashboard(
            DashboardCreateRequest(schema=schema, conversation_id=None), owner_id
        )
        self._audit(
            copied.id,
            owner_id,
            "dashboard.copied",
            details={"source_dashboard_id": dashboard_id},
        )
        return copied

    def set_archived(
        self,
        dashboard_id: str,
        expected_revision: int,
        owner_id: Optional[str],
        *,
        archived: bool,
    ) -> DashboardRecord:
        record = self.get_dashboard(dashboard_id, owner_id)
        self.require_permission(dashboard_id, owner_id, DashboardAction.EDIT)
        schema = _model_copy(record.schema_payload, deep=True)
        target = DashboardStatus.ARCHIVED if archived else DashboardStatus.DRAFT
        schema.dashboard.status = target
        schema.dashboard.updated_at = datetime.now()
        entity = self.dao.update_dashboard_status(
            dashboard_id,
            None if self.authorization is not None else self._owner(owner_id),
            expected_revision,
            status=target.value,
            schema_json=self._serialize_schema(schema),
            version_source="archive" if archived else "unarchive",
            version_actor_id=self._owner(owner_id),
        )
        self._audit(
            dashboard_id,
            owner_id,
            "dashboard.archived" if archived else "dashboard.restored",
            details={"revision": entity.current_revision},
        )
        return self._to_record(entity)

    def list_revisions(
        self, dashboard_id: str, owner_id: Optional[str]
    ) -> List[DashboardRevisionRecord]:
        self.require_permission(dashboard_id, owner_id, DashboardAction.VIEW)
        return [
            DashboardRevisionRecord(
                dashboard_id=item.dashboard_id,
                published_revision=item.revision,
                published_at=item.gmt_published,
            )
            for item in self.dao.list_published_revisions(dashboard_id)
        ]

    def list_edit_versions(
        self,
        dashboard_id: str,
        owner_id: Optional[str],
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> List[DashboardEditVersionRecord]:
        self.require_permission(dashboard_id, owner_id, DashboardAction.VIEW)
        return [
            DashboardEditVersionRecord(
                dashboard_id=item.dashboard_id,
                revision=item.revision,
                source=item.source,
                actor_id=item.actor_id,
                operation_id=item.operation_id,
                created_at=item.gmt_created,
            )
            for item in self.dao.list_edit_versions(
                dashboard_id, limit=limit, offset=offset
            )
        ]

    def get_edit_version(
        self,
        dashboard_id: str,
        revision: int,
        owner_id: Optional[str],
    ) -> DashboardEditVersionDetail:
        self.require_permission(dashboard_id, owner_id, DashboardAction.VIEW)
        item = self.dao.get_edit_version(dashboard_id, revision)
        if item is None:
            raise DashboardNotFoundError(
                f"Dashboard edit version {dashboard_id}/{revision}"
            )
        return DashboardEditVersionDetail(
            dashboard_id=item.dashboard_id,
            revision=item.revision,
            source=item.source,
            actor_id=item.actor_id,
            operation_id=item.operation_id,
            created_at=item.gmt_created,
            schema=self._parse_schema(item.schema_json),
        )

    def restore_edit_version(
        self,
        dashboard_id: str,
        revision: int,
        expected_revision: int,
        owner_id: Optional[str],
    ) -> DashboardRecord:
        self.require_permission(dashboard_id, owner_id, DashboardAction.EDIT)
        item = self.dao.get_edit_version(dashboard_id, revision)
        if item is None:
            raise DashboardNotFoundError(
                f"Dashboard edit version {dashboard_id}/{revision}"
            )
        schema = self._parse_schema(item.schema_json)
        schema.dashboard.id = dashboard_id
        schema.dashboard.status = DashboardStatus.DRAFT
        schema.dashboard.updated_at = datetime.now()
        self.authorize_schema_sources(owner_id, schema)
        validation = self.validate_schema(schema, execute_queries=False)
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)
        entity = self.dao.update_dashboard_status(
            dashboard_id,
            None if self.authorization is not None else self._owner(owner_id),
            expected_revision,
            status=DashboardStatus.DRAFT.value,
            schema_json=self._serialize_schema(schema),
            version_source="edit_version_restore",
            version_actor_id=self._owner(owner_id),
        )
        self._audit(
            dashboard_id,
            owner_id,
            "dashboard.edit_version.restored",
            target_type="edit_version",
            target_id=str(revision),
            details={"new_revision": entity.current_revision},
        )
        return self._to_record(entity)

    def get_latest_published_snapshot(
        self, dashboard_id: str, owner_id: Optional[str]
    ) -> DashboardSnapshot:
        """Return the newest immutable data snapshot without executing SQL again."""

        self.require_permission(dashboard_id, owner_id, DashboardAction.VIEW)
        revision = self.dao.get_latest_published_revision(dashboard_id)
        if not revision:
            raise DashboardNotFoundError(
                f"Published snapshot for dashboard {dashboard_id}"
            )
        snapshot = model_validate_compat(
            DashboardSnapshot, json.loads(revision.snapshot_json)
        )
        snapshot.publication_datasets = {}
        return snapshot

    def restore_revision(
        self,
        dashboard_id: str,
        published_revision: int,
        expected_revision: int,
        owner_id: Optional[str],
    ) -> DashboardRecord:
        self.require_permission(dashboard_id, owner_id, DashboardAction.EDIT)
        revision = self.dao.get_published_revision(dashboard_id, published_revision)
        if revision is None:
            raise DashboardNotFoundError(
                f"Published revision {dashboard_id}/{published_revision}"
            )
        schema = self._parse_schema(revision.schema_json)
        schema.dashboard.id = dashboard_id
        schema.dashboard.status = DashboardStatus.DRAFT
        schema.dashboard.updated_at = datetime.now()
        entity = self.dao.update_dashboard_status(
            dashboard_id,
            None if self.authorization is not None else self._owner(owner_id),
            expected_revision,
            status=DashboardStatus.DRAFT.value,
            schema_json=self._serialize_schema(schema),
            version_source="published_revision_restore",
            version_actor_id=self._owner(owner_id),
        )
        self._audit(
            dashboard_id,
            owner_id,
            "dashboard.revision.restored",
            target_type="publication",
            target_id=str(published_revision),
            details={"new_revision": entity.current_revision},
        )
        return self._to_record(entity)

    def require_permission(
        self,
        dashboard_id: str,
        actor_id: Optional[str],
        action: DashboardAction,
        schema: Optional[DashboardSchemaV1] = None,
    ) -> DashboardEntity:
        source_ids = (
            self._schema_data_source_ids(schema)
            if action == DashboardAction.QUERY and schema is not None
            else None
        )
        return self._authorized_entity(
            dashboard_id,
            actor_id,
            action,
            data_source_ids=source_ids,
        )

    def get_permissions(
        self, dashboard_id: str, actor_id: Optional[str]
    ) -> DashboardPermissionRecord:
        if self.authorization is None:
            self._authorized_entity(dashboard_id, actor_id, DashboardAction.VIEW)
            return DashboardPermissionRecord(
                dashboard_id=dashboard_id,
                actor_id=self._owner(actor_id),
                role=DashboardRole.OWNER,
                actions=DashboardAuthorizationService.actions_for_role(
                    DashboardRole.OWNER
                ),
            )
        return self.authorization.permissions(dashboard_id, self._owner(actor_id))

    def list_members(
        self, dashboard_id: str, actor_id: Optional[str]
    ) -> List[DashboardMemberRecord]:
        if self.authorization is None:
            raise RuntimeError("Dashboard authorization is not configured.")
        return self.authorization.list_members(dashboard_id, self._owner(actor_id))

    def upsert_member(
        self,
        dashboard_id: str,
        actor_id: Optional[str],
        principal_id: str,
        role: DashboardRole,
    ) -> DashboardMemberRecord:
        if self.authorization is None:
            raise RuntimeError("Dashboard authorization is not configured.")
        return self.authorization.upsert_member(
            dashboard_id,
            self._owner(actor_id),
            principal_id,
            role,
        )

    def remove_member(
        self, dashboard_id: str, actor_id: Optional[str], principal_id: str
    ) -> bool:
        if self.authorization is None:
            raise RuntimeError("Dashboard authorization is not configured.")
        return self.authorization.remove_member(
            dashboard_id, self._owner(actor_id), principal_id
        )

    def list_audit(
        self,
        dashboard_id: str,
        actor_id: Optional[str],
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> List[DashboardAuditRecord]:
        if self.authorization is None:
            raise RuntimeError("Dashboard authorization is not configured.")
        return self.authorization.list_audit(
            dashboard_id,
            self._owner(actor_id),
            limit=limit,
            offset=offset,
        )

    def update_dashboard(
        self,
        dashboard_id: str,
        schema: DashboardSchemaV1,
        expected_revision: int,
        owner_id: Optional[str],
    ) -> DashboardRecord:
        return self._update_dashboard(
            dashboard_id,
            schema,
            expected_revision,
            owner_id,
            allow_errored_widgets=False,
        )

    def update_agent_dashboard(
        self,
        dashboard_id: str,
        schema: DashboardSchemaV1,
        expected_revision: int,
        owner_id: Optional[str],
    ) -> DashboardRecord:
        """Persist a partial Agent draft without weakening normal updates.

        Only server-created widget error markers may skip query validation.
        This method is deliberately not exposed through the public REST API.
        """

        return self._update_dashboard(
            dashboard_id,
            schema,
            expected_revision,
            owner_id,
            allow_errored_widgets=True,
        )

    def _update_dashboard(
        self,
        dashboard_id: str,
        schema: DashboardSchemaV1,
        expected_revision: int,
        owner_id: Optional[str],
        *,
        allow_errored_widgets: bool,
    ) -> DashboardRecord:
        existing = self._authorized_entity(dashboard_id, owner_id, DashboardAction.EDIT)
        payload = _model_copy(schema, deep=True)
        if payload.dashboard.id and payload.dashboard.id != dashboard_id:
            raise DashboardSchemaValidationError(
                [
                    ValidationIssue(
                        path="dashboard.id",
                        code="dashboard_id_mismatch",
                        message="The schema dashboard id does not match the URL id.",
                    )
                ]
            )
        payload.dashboard.id = dashboard_id
        payload.dashboard.status = DashboardStatus.DRAFT
        payload.dashboard.updated_at = datetime.now()
        payload.metadata.conversation_id = (
            payload.metadata.conversation_id or existing.conversation_id
        )
        payload.metadata.source_turn_id = (
            payload.metadata.source_turn_id or existing.source_turn_id
        )
        enrich_schema_lineage(payload)
        self.authorize_schema_sources(owner_id, payload)
        validation = self.validate_schema(
            payload,
            execute_queries=False,
            skip_errored_widgets=allow_errored_widgets,
        )
        if not validation.valid:
            raise DashboardSchemaValidationError(validation.issues)
        check_generation_deadline()
        entity = self.dao.update_dashboard(
            dashboard_id,
            None if self.authorization is not None else self._owner(owner_id),
            expected_revision,
            title=payload.dashboard.title,
            description=payload.dashboard.description,
            data_source_id=payload.dashboard.data_source_id,
            schema_json=self._serialize_schema(payload),
            promote_to_asset=not allow_errored_widgets,
            version_source=("agent_edit" if allow_errored_widgets else "manual_save"),
            version_actor_id=self._owner(owner_id),
        )
        self._audit(
            dashboard_id,
            owner_id,
            "dashboard.updated",
            details={
                "revision": entity.current_revision,
                "agent_generated": allow_errored_widgets,
            },
        )
        return self._to_record(entity)

    def validate_schema(
        self,
        schema: DashboardSchemaV1,
        *,
        execute_queries: bool = False,
        filters: Optional[Dict[str, Any]] = None,
        skip_errored_widgets: bool = False,
        require_publication_bindings: bool = False,
    ) -> DashboardValidationResult:
        missing_bindings = (
            self.publication_service.missing_bindings(schema)
            if require_publication_bindings
            else []
        )
        result = self.query_executor.validate_schema(
            schema,
            # A missing frozen-data contract is a deterministic precondition.
            # Do not run database queries for a request that must be rejected.
            execute_queries=execute_queries and not missing_bindings,
            filters=filters,
            skip_errored_widgets=skip_errored_widgets,
        )
        if require_publication_bindings:
            result.issues.extend(
                ValidationIssue(
                    path=f"widgets.{widget_id}.publication",
                    code="publication_binding_required",
                    message=(
                        "This widget has no frozen-data publication binding. "
                        "Configure it for interactive share-page filtering "
                        "before publishing."
                    ),
                )
                for widget_id in missing_bindings
            )
            if not missing_bindings:
                try:
                    self.publication_service.validate_coverage(schema)
                except DashboardPublicationError as exc:
                    result.issues.append(
                        ValidationIssue(
                            path="publication",
                            code="publication_coverage_failed",
                            message=str(exc),
                        )
                    )
                if not any(issue.severity == "error" for issue in result.issues):
                    materialization_failures = (
                        self.publication_service.validate_materialization(
                            schema, self.query_executor
                        )
                    )
                    result.issues.extend(
                        ValidationIssue(
                            path=f"widgets.{widget_id}.publication",
                            code="publication_materialization_failed",
                            message=message,
                        )
                        for widget_id, message in materialization_failures.items()
                    )
            result.valid = not any(issue.severity == "error" for issue in result.issues)
        return result

    def validate_widget_query(
        self,
        schema: DashboardSchemaV1,
        widget_id: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> WidgetQueryResult:
        """Safely execute one in-memory widget before an Agent draft is saved."""

        return self.query_executor.execute_widget(schema, widget_id, filters or {})

    def preview_widget(
        self,
        dashboard_id: str,
        widget_id: str,
        filters: Dict[str, Any],
        owner_id: Optional[str],
    ) -> WidgetQueryResult:
        record = self.get_dashboard(dashboard_id, owner_id)
        self.require_permission(
            dashboard_id,
            owner_id,
            DashboardAction.QUERY,
            record.schema_payload,
        )
        return self.query_executor.execute_widget(
            record.schema_payload, widget_id, filters
        )

    def refresh_dashboard(
        self, dashboard_id: str, filters: Dict[str, Any], owner_id: Optional[str]
    ) -> DashboardSnapshot:
        record = self.get_dashboard(dashboard_id, owner_id)
        schema = record.schema_payload
        self.require_permission(dashboard_id, owner_id, DashboardAction.QUERY, schema)
        results = self.query_executor.execute_dashboard(schema, filters)
        snapshot = DashboardSnapshot(
            dashboard_id=dashboard_id,
            refreshed_at=datetime.now(),
            filters=self.query_executor.filter_values(schema, filters),
            widgets=results,
        )
        self._audit(
            dashboard_id,
            owner_id,
            "dashboard.refreshed",
            details={
                "widget_count": len(results),
                "failed_widget_count": sum(
                    1 for item in results.values() if item.error is not None
                ),
            },
        )
        return snapshot

    def publish_dashboard(
        self,
        dashboard_id: str,
        expected_revision: int,
        filters: Dict[str, Any],
        owner_id: Optional[str],
        *,
        share_expires_in_seconds: Optional[int] = None,
        allow_static_widgets: bool = False,
    ) -> DashboardPublishResponse:
        record = self.get_dashboard(dashboard_id, owner_id)
        self.require_permission(dashboard_id, owner_id, DashboardAction.PUBLISH)
        self.require_permission(
            dashboard_id,
            owner_id,
            DashboardAction.QUERY,
            record.schema_payload,
        )
        if record.current_revision != expected_revision:
            raise DashboardConflictError(
                f"Dashboard revision changed from {expected_revision} "
                f"to {record.current_revision}."
            )
        missing_publication_bindings = self.publication_service.missing_bindings(
            record.schema_payload
        )
        if missing_publication_bindings and not allow_static_widgets:
            # This contract failure is deterministic.  Stop before any normal
            # widget query runs so the caller receives one clean set of repair
            # targets instead of database activity followed by duplicate errors.
            raise DashboardPublishValidationError(
                DashboardValidationResult(
                    valid=False,
                    issues=[
                        ValidationIssue(
                            path=f"widgets.{widget_id}.publication",
                            code="publication_binding_required",
                            message=(
                                "This widget has no frozen-data publication binding. "
                                "Configure it for interactive share-page filtering "
                                "before publishing."
                            ),
                        )
                        for widget_id in missing_publication_bindings
                    ],
                )
            )
        validation = self.validate_schema(
            record.schema_payload,
            execute_queries=True,
            filters=filters,
            require_publication_bindings=not allow_static_widgets,
        )
        if not validation.valid:
            raise DashboardPublishValidationError(validation)
        snapshot = self.refresh_dashboard(dashboard_id, filters, owner_id)
        failed = [item for item in snapshot.widgets.values() if item.error]
        if failed:
            result = DashboardValidationResult(
                valid=False,
                issues=[
                    ValidationIssue(
                        path=f"widgets.{item.widget_id}",
                        code="widget_refresh_failed",
                        message=item.error.message if item.error else "Unknown error",
                    )
                    for item in failed
                ],
            )
            raise DashboardPublishValidationError(result)

        # Materialization is performed with the owner's normal data-source
        # permission, then frozen into the immutable revision.  Public requests
        # never receive this executor or a connector.
        try:
            snapshot.publication_datasets = self.publication_service.materialize(
                record.schema_payload,
                self.query_executor,
                allow_static_widgets=allow_static_widgets,
            )
        except DashboardPublicationError as exc:
            raise DashboardPublishValidationError(
                DashboardValidationResult(
                    valid=False,
                    issues=[
                        ValidationIssue(
                            path="publication",
                            code="publication_materialization_failed",
                            message=str(exc),
                        )
                    ],
                )
            ) from exc

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expires_at = self._share_expiry(share_expires_in_seconds)
        schema = _model_copy(record.schema_payload, deep=True)
        schema.dashboard.status = DashboardStatus.PUBLISHED
        schema_json = self._serialize_schema(schema)
        snapshot_json = _json_dumps(model_dump_compat(snapshot))
        if len(snapshot_json.encode("utf-8")) > MAX_PUBLISHED_SNAPSHOT_BYTES:
            raise DashboardPublishValidationError(
                DashboardValidationResult(
                    valid=False,
                    issues=[
                        ValidationIssue(
                            path="snapshot",
                            code="snapshot_too_large",
                            message=(
                                "Published snapshot exceeds the 10 MiB immutable "
                                "storage limit. Reduce widget rows or columns."
                            ),
                        )
                    ],
                )
            )
        self.dao.remember_share_token(token)
        revision, published_dashboard = self.dao.publish_dashboard(
            dashboard_id,
            None if self.authorization is not None else self._owner(owner_id),
            expected_revision,
            schema_json=schema_json,
            snapshot_json=snapshot_json,
            validation_json=_json_dumps(model_dump_compat(validation)),
            share_token_hash=token_hash,
            public_slug=secrets.token_urlsafe(24),
            share_created_by=self._owner(owner_id),
            share_expires_at=expires_at,
        )
        response = DashboardPublishResponse(
            dashboard_id=dashboard_id,
            published_revision=revision.revision,
            share_token=token,
            share_path=f"/dashboard-share/{token}",
            latest_share_path=(
                f"/dashboard-share/{published_dashboard.public_slug}"
                if published_dashboard.public_slug
                else None
            ),
            published_at=revision.gmt_published,
            expires_at=expires_at,
        )
        self._audit(
            dashboard_id,
            owner_id,
            "dashboard.published",
            details={
                "published_revision": revision.revision,
                "static_widget_count": len(missing_publication_bindings)
                if allow_static_widgets
                else 0,
            },
        )
        return response

    @staticmethod
    def _share_expiry(expires_in_seconds: Optional[int]) -> Optional[datetime]:
        if expires_in_seconds is None:
            return None
        return datetime.now() + timedelta(seconds=expires_in_seconds)

    @staticmethod
    def _share_record(item, *, now: Optional[datetime] = None) -> DashboardShareRecord:
        now = now or datetime.now()
        return DashboardShareRecord(
            id=item.id,
            dashboard_id=item.dashboard_id,
            published_revision=item.revision,
            created_by=item.created_by,
            created_at=item.gmt_created,
            expires_at=item.expires_at,
            revoked_at=item.revoked_at,
            active=item.revoked_at is None
            and (item.expires_at is None or item.expires_at > now),
        )

    def list_publications(
        self, dashboard_id: str, actor_id: Optional[str]
    ) -> List[DashboardShareRecord]:
        self.require_permission(dashboard_id, actor_id, DashboardAction.PUBLISH)
        return [self._share_record(item) for item in self.dao.list_shares(dashboard_id)]

    def rotate_publication(
        self,
        dashboard_id: str,
        published_revision: int,
        actor_id: Optional[str],
        *,
        share_expires_in_seconds: Optional[int] = None,
    ) -> DashboardPublishResponse:
        self.require_permission(dashboard_id, actor_id, DashboardAction.PUBLISH)
        token = secrets.token_urlsafe(32)
        expires_at = self._share_expiry(share_expires_in_seconds)
        self.dao.remember_share_token(token)
        share = self.dao.rotate_share(
            dashboard_id,
            published_revision,
            hashlib.sha256(token.encode("utf-8")).hexdigest(),
            created_by=self._owner(actor_id),
            expires_at=expires_at,
        )
        dashboard = self.dao.get_dashboard_by_id(dashboard_id)
        self._audit(
            dashboard_id,
            actor_id,
            "dashboard.publication.rotated",
            target_type="publication",
            target_id=str(published_revision),
            details={"expires_at": expires_at},
        )
        return DashboardPublishResponse(
            dashboard_id=dashboard_id,
            published_revision=published_revision,
            share_token=token,
            share_path=f"/dashboard-share/{token}",
            latest_share_path=(
                f"/dashboard-share/{dashboard.public_slug}"
                if dashboard is not None and dashboard.public_slug
                else None
            ),
            published_at=share.gmt_created,
            expires_at=expires_at,
        )

    def revoke_publication(
        self, dashboard_id: str, published_revision: int, actor_id: Optional[str]
    ) -> bool:
        self.require_permission(dashboard_id, actor_id, DashboardAction.PUBLISH)
        revoked = self.dao.revoke_shares(dashboard_id, published_revision)
        if not revoked:
            raise DashboardNotFoundError(
                f"Active publication {dashboard_id}/{published_revision}"
            )
        self._audit(
            dashboard_id,
            actor_id,
            "dashboard.publication.revoked",
            target_type="publication",
            target_id=str(published_revision),
        )
        return True

    def _resolve_public_revision(self, token: str):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        revision = self.dao.get_active_published_by_token_hash(token_hash)
        is_latest_link = False
        if revision is None:
            dashboard = self.dao.get_dashboard_by_public_slug(token)
            if dashboard is not None:
                revision = self.dao.get_latest_published_revision(dashboard.id)
                is_latest_link = revision is not None
        if revision is None:
            raise DashboardNotFoundError("Published dashboard")
        if not is_latest_link:
            self.dao.remember_share_token(token)
        return revision, is_latest_link

    def get_public_snapshot(self, token: str) -> PublicDashboardSnapshot:
        revision, is_latest_link = self._resolve_public_revision(token)
        stored_snapshot = model_validate_compat(
            DashboardSnapshot, json.loads(revision.snapshot_json)
        )
        public_snapshot = _model_copy(stored_snapshot, deep=True)
        public_snapshot.publication_datasets = {}
        return PublicDashboardSnapshot(
            dashboard_id=revision.dashboard_id,
            published_revision=revision.revision,
            schema=self._parse_schema(revision.schema_json),
            snapshot=public_snapshot,
            published_at=revision.gmt_published,
            is_latest_link=is_latest_link,
        )

    def filter_public_snapshot(
        self, token: str, filters: Dict[str, Any]
    ) -> PublicDashboardFilterResponse:
        """Filter a frozen publication dataset without opening a database."""

        revision, _ = self._resolve_public_revision(token)
        schema = self._parse_schema(revision.schema_json)
        stored_snapshot = model_validate_compat(
            DashboardSnapshot, json.loads(revision.snapshot_json)
        )
        return self.publication_service.filter_snapshot(
            schema, stored_snapshot, filters
        )
