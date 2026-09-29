"""REST API for Dashboard Schema v1 drafts and published snapshots."""

import asyncio
import io
import zipfile
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import StreamingResponse

from dbgpt_app.openapi.api_view_model import Result
from dbgpt_serve.scheduled_task.api.endpoints import (
    get_service as get_scheduled_task_service,
)
from dbgpt_serve.scheduled_task.api.schemas import (
    CreateTaskRequest,
    DashboardRefreshPayload,
    RunResponse,
    TaskResponse,
    UpdateTaskRequest,
)
from dbgpt_serve.scheduled_task.service.chat_replay_runner import run_scheduled_task
from dbgpt_serve.scheduled_task.service.service import ScheduledTaskService
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

from .annotation_generation import (
    AnnotationGenerationRequest,
    generate_annotation_proposal,
)
from .annotation_intents import (
    AnnotationIntentBatch,
    AnnotationIntentResolution,
    resolve_annotation_intents,
)
from .annotations import DashboardAnnotationService
from .catalog import instantiate_template, preview_template
from .catalog_ai import (
    TemplateAdaptRequest,
    adapt_template,
    create_adapted_template,
    template_features,
)
from .catalog_source import TemplateSourceMapping, inspect_source
from .collaboration import (
    DashboardCollaborationService,
    DashboardPatchError,
    collaboration_hub,
    ticket_store,
)
from .covers import CoverService, DashboardCoverRequest
from .folders import FolderService
from .identity import (
    DashboardIdentityError,
    DashboardIdentityProvider,
    get_dashboard_identity_provider,
)
from .legacy_adapter import adapt_legacy_report
from .live_share import LiveShareService
from .models import (
    DashboardAccessDeniedError,
    DashboardConflictError,
    DashboardNotFoundError,
)
from .publication import DashboardPublicationError
from .query_logic import QueryLogicRequest, describe_query_logic
from .schemas import (
    DashboardAction,
    DashboardAnnotationApplyRequest,
    DashboardAnnotationApplyResponse,
    DashboardAnnotationCreateRequest,
    DashboardAnnotationRecord,
    DashboardArtifactBundle,
    DashboardAssetState,
    DashboardAuditRecord,
    DashboardCollaborationTicket,
    DashboardCollaborationTicketRequest,
    DashboardCopyRequest,
    DashboardCreateRequest,
    DashboardEditVersionDetail,
    DashboardEditVersionRecord,
    DashboardListItem,
    DashboardListPage,
    DashboardMemberRecord,
    DashboardMemberUpsertRequest,
    DashboardOperationLogRecord,
    DashboardOperationRequest,
    DashboardOperationResponse,
    DashboardOrigin,
    DashboardPermissionRecord,
    DashboardPublishRequest,
    DashboardPublishResponse,
    DashboardRecord,
    DashboardRefreshRequest,
    DashboardRevisionRecord,
    DashboardScheduleCreateRequest,
    DashboardScheduleToggleRequest,
    DashboardScheduleUpdateRequest,
    DashboardSchemaV1,
    DashboardShareRecord,
    DashboardShareRotateRequest,
    DashboardSnapshot,
    DashboardStateRequest,
    DashboardStatus,
    DashboardTargetResolution,
    DashboardTargetResolutionRequest,
    DashboardUpdateRequest,
    DashboardValidateRequest,
    DashboardValidationResult,
    DashboardWidgetPreviewRequest,
    LegacyDashboardImportRequest,
    PublicDashboardFilterRequest,
    PublicDashboardFilterResponse,
    PublicDashboardSnapshot,
    ValidationIssue,
    WidgetQueryResult,
    model_dump_compat,
)
from .service import (
    DashboardPublishValidationError,
    DashboardSchemaValidationError,
    DashboardService,
)
from .target_resolution import resolve_dashboard_target

router = APIRouter(prefix="/v1")


def get_dashboard_service() -> DashboardService:
    return DashboardService()


def get_collaboration_service() -> DashboardCollaborationService:
    return DashboardCollaborationService()


def get_annotation_service() -> DashboardAnnotationService:
    return DashboardAnnotationService()


def _user_id(
    user: UserRequest, provider: DashboardIdentityProvider | None = None
) -> str:
    try:
        return (provider or get_dashboard_identity_provider()).resolve(user)
    except DashboardIdentityError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def _not_found(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _forbidden(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


def _schema_error(exc: DashboardSchemaValidationError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=[
            issue.model_dump() if hasattr(issue, "model_dump") else issue.dict()
            for issue in exc.issues
        ],
    )


@router.post("/dashboards", response_model=Result[DashboardRecord])
def create_dashboard(
    request: DashboardCreateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(service.create_dashboard(request, _user_id(user)))
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc


@router.get("/dashboards", response_model=Result[List[DashboardListItem]])
def list_dashboards(
    conversation_id: Optional[str] = Query(default=None, max_length=255),
    origin: Optional[DashboardOrigin] = Query(default=None),
    exclude_origin: Optional[DashboardOrigin] = Query(default=None),
    asset_state: Optional[DashboardAssetState] = Query(default=None),
    dashboard_status: Optional[DashboardStatus] = Query(default=None, alias="status"),
    include_generated: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return Result.succ(
        service.list_dashboards(
            _user_id(user),
            conversation_id=conversation_id,
            origin=origin,
            exclude_origin=exclude_origin,
            asset_state=asset_state,
            status=dashboard_status,
            include_generated=include_generated,
            include_archived=include_archived,
        )
    )


@router.get("/dashboards/page", response_model=Result[DashboardListPage])
def page_dashboards(
    folder_id: Optional[str] = Query(default=None, max_length=64),
    search: Optional[str] = Query(default=None, max_length=255),
    dashboard_status: Optional[DashboardStatus] = Query(default=None, alias="status"),
    conversation_id: Optional[str] = Query(default=None, max_length=255),
    origin: Optional[DashboardOrigin] = Query(default=None),
    exclude_origin: Optional[DashboardOrigin] = Query(default=None),
    asset_state: Optional[DashboardAssetState] = Query(default=None),
    include_generated: bool = Query(default=False),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return Result.succ(
        service.list_dashboard_page(
            _user_id(user),
            search=search,
            folder_id=folder_id,
            status=dashboard_status,
            conversation_id=conversation_id,
            origin=origin,
            exclude_origin=exclude_origin,
            asset_state=asset_state,
            include_generated=include_generated,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
    )


@router.post("/dashboards/import/legacy", response_model=Result[DashboardRecord])
def import_legacy_dashboard(
    request: LegacyDashboardImportRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Copy an old chat-dashboard report into a new editable Schema v1 draft."""

    try:
        schema = adapt_legacy_report(
            request.report, request.data_source_id, request.conversation_id
        )
        return Result.succ(
            service.create_dashboard(
                DashboardCreateRequest(
                    schema=schema, conversation_id=schema.metadata.conversation_id
                ),
                _user_id(user),
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/dashboards/schema", response_model=Result[Dict[str, Any]])
def get_dashboard_schema():
    """Expose the exact Pydantic-generated JSON Schema used by the server."""

    if hasattr(DashboardSchemaV1, "model_json_schema"):
        schema = DashboardSchemaV1.model_json_schema()
    else:  # pragma: no cover - compatibility with older Pydantic
        schema = DashboardSchemaV1.schema()
    return Result.succ(schema)


@router.get("/dashboards/{dashboard_id}", response_model=Result[DashboardRecord])
def get_dashboard(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(service.get_dashboard(dashboard_id, _user_id(user)))
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post("/dashboards/{dashboard_id}/assistant-task")
def ensure_dashboard_assistant_task(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        actor = _user_id(user)
        service.require_permission(dashboard_id, actor, DashboardAction.EDIT)
        return Result.succ(
            {
                "conversation_id": service.dao.ensure_assistant_conversation(
                    dashboard_id, actor
                )
            }
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/resolve-target",
    response_model=Result[DashboardTargetResolution],
)
def resolve_dashboard_reference(
    dashboard_id: str,
    request: DashboardTargetResolutionRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Resolve a natural widget reference without allowing ambiguous edits."""

    try:
        record = service.get_dashboard(dashboard_id, _user_id(user))
        return Result.succ(
            resolve_dashboard_target(
                record.schema_payload,
                request.reference,
                selected_widget_id=request.selected_widget_id,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get(
    "/dashboards/{dashboard_id}/versions",
    response_model=Result[List[DashboardEditVersionRecord]],
)
def list_dashboard_edit_versions(
    dashboard_id: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.list_edit_versions(
                dashboard_id,
                _user_id(user),
                limit=limit,
                offset=offset,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get(
    "/dashboards/{dashboard_id}/versions/{revision}",
    response_model=Result[DashboardEditVersionDetail],
)
def get_dashboard_edit_version(
    dashboard_id: str,
    revision: int,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.get_edit_version(dashboard_id, revision, _user_id(user))
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/versions/{revision}/restore",
    response_model=Result[DashboardRecord],
)
def restore_dashboard_edit_version(
    dashboard_id: str,
    revision: int,
    request: DashboardStateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.restore_edit_version(
                dashboard_id,
                revision,
                request.expected_revision,
                _user_id(user),
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc


@router.get(
    "/dashboards/{dashboard_id}/artifacts",
    response_model=Result[DashboardArtifactBundle],
)
def get_dashboard_artifacts(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(service.build_artifact_bundle(dashboard_id, _user_id(user)))
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get("/dashboards/{dashboard_id}/export")
def export_dashboard_project(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        bundle = service.build_artifact_bundle(dashboard_id, _user_id(user))
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for artifact in bundle.files:
            archive.writestr(f"{bundle.root}/{artifact.path}", artifact.content)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{bundle.root}.zip"'},
    )


@router.get(
    "/dashboards/{dashboard_id}/snapshot",
    response_model=Result[DashboardSnapshot],
)
def get_latest_dashboard_snapshot(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Restore the newest published data snapshot in the authenticated editor."""

    try:
        return Result.succ(
            service.get_latest_published_snapshot(dashboard_id, _user_id(user))
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post("/dashboards/{dashboard_id}/copy", response_model=Result[DashboardRecord])
def copy_dashboard(
    dashboard_id: str,
    request: DashboardCopyRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.copy_dashboard(dashboard_id, request, _user_id(user))
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/archive", response_model=Result[DashboardRecord]
)
def archive_dashboard(
    dashboard_id: str,
    request: DashboardStateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.set_archived(
                dashboard_id,
                request.expected_revision,
                _user_id(user),
                archived=True,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/restore", response_model=Result[DashboardRecord]
)
def restore_dashboard(
    dashboard_id: str,
    request: DashboardStateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.set_archived(
                dashboard_id,
                request.expected_revision,
                _user_id(user),
                archived=False,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get(
    "/dashboards/{dashboard_id}/revisions",
    response_model=Result[List[DashboardRevisionRecord]],
)
def list_dashboard_revisions(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(service.list_revisions(dashboard_id, _user_id(user)))
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/revisions/{published_revision}/restore",
    response_model=Result[DashboardRecord],
)
def restore_dashboard_revision(
    dashboard_id: str,
    published_revision: int,
    request: DashboardStateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.restore_revision(
                dashboard_id,
                published_revision,
                request.expected_revision,
                _user_id(user),
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.put("/dashboards/{dashboard_id}", response_model=Result[DashboardRecord])
def update_dashboard(
    dashboard_id: str,
    request: DashboardUpdateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.update_dashboard(
                dashboard_id,
                request.schema_payload,
                request.expected_revision,
                _user_id(user),
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/operations",
    response_model=Result[DashboardOperationResponse],
)
async def apply_dashboard_operation(
    dashboard_id: str,
    request: DashboardOperationRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardCollaborationService = Depends(get_collaboration_service),
):
    """Apply one idempotent, revision-checked collaboration operation."""

    try:
        response = service.apply_operation(dashboard_id, request, _user_id(user))
        await collaboration_hub.broadcast(
            dashboard_id,
            {
                "type": "operation.accepted",
                "payload": model_dump_compat(response),
            },
        )
        return Result.succ(response)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc
    except DashboardPatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/dashboards/{dashboard_id}/operations",
    response_model=Result[List[DashboardOperationLogRecord]],
)
def list_dashboard_operations(
    dashboard_id: str,
    after_revision: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=500),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardCollaborationService = Depends(get_collaboration_service),
):
    """Return accepted operations so a reconnecting client can catch up."""

    try:
        return Result.succ(
            service.list_operations(
                dashboard_id,
                _user_id(user),
                after_revision=after_revision,
                limit=limit,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/annotation-intents",
    response_model=Result[AnnotationIntentResolution],
)
async def resolve_dashboard_annotation_intents(
    dashboard_id: str,
    request: AnnotationIntentBatch,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        service._authorized_entity(dashboard_id, _user_id(user), DashboardAction.EDIT)
        record = service.get_dashboard(dashboard_id, _user_id(user))
        schema = record.schema_payload
        context = {
            "dashboard": schema.dashboard.model_dump(mode="json"),
            "filters": [item.model_dump(mode="json") for item in schema.filters],
            "widgets": [
                item.model_dump(mode="json", exclude={"publication"})
                for item in schema.widgets
            ],
        }
        return Result.succ(
            await resolve_annotation_intents(request, dashboard_context=context)
        )
    except HTTPException:
        raise
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="意图识别暂时不可用，批注已保留，请稍后重试。",
        ) from exc


@router.post(
    "/dashboards/{dashboard_id}/query-logic",
    response_model=Result[Dict[str, Any]],
)
def get_dashboard_query_logic(
    dashboard_id: str,
    request: QueryLogicRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        service._authorized_entity(dashboard_id, _user_id(user), DashboardAction.VIEW)
        record = service.get_dashboard(dashboard_id, _user_id(user))
        sources = {record.schema_payload.dashboard.data_source_id} | {
            widget.query.data_source_id for widget in record.schema_payload.widgets
        }
        if request.data_source_id not in sources:
            raise HTTPException(status_code=422, detail="请选择当前看板使用的数据源。")
        connector = service.query_executor._get_connector(request.data_source_id)
        dialect = service.query_executor._dialect(connector)
        return Result.succ(describe_query_logic(request.sql, dialect))
    except HTTPException:
        raise
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail="暂时无法解析这条查询，请查看原始 SQL。"
        ) from exc


@router.get(
    "/dashboards/{dashboard_id}/annotations",
    response_model=Result[List[DashboardAnnotationRecord]],
)
def list_dashboard_annotations(
    dashboard_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardAnnotationService = Depends(get_annotation_service),
):
    try:
        return Result.succ(
            service.list_annotations(
                dashboard_id, _user_id(user), limit=limit, offset=offset
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/annotations",
    response_model=Result[DashboardAnnotationRecord],
)
def create_dashboard_annotation(
    dashboard_id: str,
    request: DashboardAnnotationCreateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardAnnotationService = Depends(get_annotation_service),
):
    try:
        return Result.succ(
            service.create_annotation(dashboard_id, request, _user_id(user))
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardPatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/dashboards/{dashboard_id}/annotations/{annotation_id}/generate",
    response_model=Result[DashboardAnnotationRecord],
)
async def generate_dashboard_annotation(
    dashboard_id: str,
    annotation_id: str,
    request: AnnotationGenerationRequest,
    http_request: Request,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardAnnotationService = Depends(get_annotation_service),
):
    try:
        return Result.succ(
            await generate_annotation_proposal(
                service,
                dashboard_id,
                annotation_id,
                _user_id(user),
                request,
                cancelled=http_request.is_disconnected,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except (DashboardPatchError, DashboardSchemaValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="模型生成超时，批注已保留，可以重试。"
        ) from exc


@router.post(
    "/dashboards/{dashboard_id}/annotations/{annotation_id}/apply",
    response_model=Result[DashboardAnnotationApplyResponse],
)
async def apply_dashboard_annotation(
    dashboard_id: str,
    annotation_id: str,
    request: DashboardAnnotationApplyRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardAnnotationService = Depends(get_annotation_service),
):
    try:
        response = service.apply_annotation(
            dashboard_id, annotation_id, request, _user_id(user)
        )
        await collaboration_hub.broadcast(
            dashboard_id,
            {
                "type": "operation.accepted",
                "payload": model_dump_compat(response.operation),
            },
        )
        return Result.succ(response)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc
    except DashboardPatchError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class AnnotationBatchApplyRequest(DashboardAnnotationApplyRequest):
    annotation_ids: List[str] = Field(min_length=1, max_length=40)


@router.post("/dashboards/{dashboard_id}/annotations/apply-batch")
async def apply_dashboard_annotation_batch(
    dashboard_id: str,
    request: AnnotationBatchApplyRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardAnnotationService = Depends(get_annotation_service),
):
    try:
        result = service.apply_batch(
            dashboard_id, request.annotation_ids, request, _user_id(user)
        )
        await collaboration_hub.broadcast(
            dashboard_id,
            {
                "type": "operation.accepted",
                "payload": model_dump_compat(result["operation"]),
            },
        )
        return Result.succ(result)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc
    except (DashboardPatchError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/dashboards/{dashboard_id}/annotations/{annotation_id}/reject",
    response_model=Result[DashboardAnnotationRecord],
)
def reject_dashboard_annotation(
    dashboard_id: str,
    annotation_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardAnnotationService = Depends(get_annotation_service),
):
    try:
        return Result.succ(
            service.reject_annotation(dashboard_id, annotation_id, _user_id(user))
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/collaboration-ticket",
    response_model=Result[DashboardCollaborationTicket],
)
def create_collaboration_ticket(
    dashboard_id: str,
    request: DashboardCollaborationTicketRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    """Issue a one-time ticket so credentials never appear in a WebSocket URL."""

    actor_id = _user_id(user)
    try:
        service.require_permission(dashboard_id, actor_id, DashboardAction.EDIT)
        result = ticket_store.issue(dashboard_id, actor_id, request.client_id)
        service.record_audit(
            dashboard_id,
            actor_id,
            "collaboration.ticket.issued",
            details={"client_id": request.client_id, "expires_at": result.expires_at},
        )
        return Result.succ(result)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.websocket("/dashboards/{dashboard_id}/collaborate")
async def collaborate_dashboard(websocket: WebSocket, dashboard_id: str):
    """Presence and accepted-operation transport for collaborative editors."""

    ticket = websocket.query_params.get("ticket", "")
    try:
        claim = ticket_store.consume(ticket, dashboard_id)
    except DashboardPatchError:
        await websocket.close(code=4401, reason="Invalid collaboration ticket")
        return

    service = DashboardCollaborationService()
    try:
        current = service.dashboard_service.get_dashboard(dashboard_id, claim.actor_id)
        service.dashboard_service.require_permission(
            dashboard_id, claim.actor_id, DashboardAction.EDIT
        )
    except DashboardNotFoundError:
        await websocket.close(code=4404, reason="Dashboard not found")
        return
    except DashboardAccessDeniedError:
        await websocket.close(code=4403, reason="Dashboard edit access denied")
        return

    await websocket.accept()
    connection_id = await collaboration_hub.connect(
        dashboard_id, websocket, claim.actor_id, claim.client_id
    )
    await websocket.send_json(
        {
            "type": "collaboration.ready",
            "payload": {
                "dashboard_id": dashboard_id,
                "client_id": claim.client_id,
                "current_revision": current.current_revision,
            },
        }
    )
    await collaboration_hub.broadcast(
        dashboard_id,
        {
            "type": "presence.changed",
            "payload": {"participants": await collaboration_hub.presence(dashboard_id)},
        },
    )
    try:
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type") if isinstance(message, dict) else None
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message_type != "operation":
                await websocket.send_json(
                    {
                        "type": "collaboration.error",
                        "payload": {"message": "Unsupported collaboration message."},
                    }
                )
                continue
            try:
                request = DashboardOperationRequest.model_validate(
                    message.get("payload", {})
                )
                if request.client_id != claim.client_id:
                    raise DashboardPatchError(
                        "The operation client id does not match its ticket."
                    )
                response = service.apply_operation(
                    dashboard_id, request, claim.actor_id
                )
                await collaboration_hub.broadcast(
                    dashboard_id,
                    {
                        "type": "operation.accepted",
                        "payload": model_dump_compat(response),
                    },
                )
            except DashboardConflictError as exc:
                latest = service.dashboard_service.get_dashboard(
                    dashboard_id, claim.actor_id
                )
                await websocket.send_json(
                    {
                        "type": "operation.conflict",
                        "payload": {
                            "message": str(exc),
                            "current_revision": latest.current_revision,
                        },
                    }
                )
            except DashboardSchemaValidationError as exc:
                await websocket.send_json(
                    {
                        "type": "operation.rejected",
                        "payload": {
                            "issues": [model_dump_compat(item) for item in exc.issues]
                        },
                    }
                )
            except (DashboardPatchError, ValidationError, ValueError) as exc:
                await websocket.send_json(
                    {
                        "type": "operation.rejected",
                        "payload": {"message": str(exc)},
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        await collaboration_hub.disconnect(dashboard_id, connection_id)
        await collaboration_hub.broadcast(
            dashboard_id,
            {
                "type": "presence.changed",
                "payload": {
                    "participants": await collaboration_hub.presence(dashboard_id)
                },
            },
        )


@router.post(
    "/dashboards/{dashboard_id}/validate",
    response_model=Result[DashboardValidationResult],
)
def validate_dashboard(
    dashboard_id: str,
    request: DashboardValidateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        persisted = service.get_dashboard(dashboard_id, _user_id(user))
        schema = request.schema_payload or persisted.schema_payload
        service.require_permission(
            dashboard_id,
            _user_id(user),
            DashboardAction.QUERY if request.execute_queries else DashboardAction.EDIT,
            schema,
        )
        if schema.dashboard.id and schema.dashboard.id != dashboard_id:
            raise DashboardSchemaValidationError(
                [
                    ValidationIssue(
                        path="dashboard.id",
                        code="dashboard_id_mismatch",
                        message="Validation schema does not belong to this dashboard.",
                    )
                ]
            )
        if (
            schema.dashboard.data_source_id
            != persisted.schema_payload.dashboard.data_source_id
        ):
            raise DashboardSchemaValidationError(
                [
                    ValidationIssue(
                        path="dashboard.data_source_id",
                        code="validation_data_source_change_not_allowed",
                        message=(
                            "Save the dashboard before validating a different "
                            "data source."
                        ),
                    )
                ]
            )
        return Result.succ(
            service.validate_schema(
                schema,
                execute_queries=request.execute_queries,
                filters=request.filters,
                require_publication_bindings=request.require_publication_bindings,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/widgets/{widget_id}/preview",
    response_model=Result[WidgetQueryResult],
)
def preview_widget(
    dashboard_id: str,
    widget_id: str,
    request: DashboardWidgetPreviewRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        persisted = service.get_dashboard(dashboard_id, _user_id(user))
        schema = request.schema_payload or persisted.schema_payload
        service.require_permission(
            dashboard_id,
            _user_id(user),
            DashboardAction.QUERY,
            schema,
        )
        if schema.dashboard.id and schema.dashboard.id != dashboard_id:
            raise DashboardSchemaValidationError(
                [
                    ValidationIssue(
                        path="dashboard.id",
                        code="dashboard_id_mismatch",
                        message="Preview schema does not belong to this dashboard.",
                    )
                ]
            )
        if (
            schema.dashboard.data_source_id
            != persisted.schema_payload.dashboard.data_source_id
        ):
            raise DashboardSchemaValidationError(
                [
                    ValidationIssue(
                        path="dashboard.data_source_id",
                        code="preview_data_source_change_not_allowed",
                        message=(
                            "Save the dashboard before previewing a different "
                            "data source."
                        ),
                    )
                ]
            )
        return Result.succ(
            service.validate_widget_query(schema, widget_id, request.filters)
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardSchemaValidationError as exc:
        raise _schema_error(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/refresh", response_model=Result[DashboardSnapshot]
)
def refresh_dashboard(
    dashboard_id: str,
    request: DashboardRefreshRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.refresh_dashboard(dashboard_id, request.filters, _user_id(user))
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/publish",
    response_model=Result[DashboardPublishResponse],
)
def publish_dashboard(
    dashboard_id: str,
    request: DashboardPublishRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.publish_dashboard(
                dashboard_id,
                request.expected_revision,
                request.filters,
                _user_id(user),
                share_expires_in_seconds=request.share_expires_in_seconds,
                allow_static_widgets=request.allow_static_widgets,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardConflictError as exc:
        raise _conflict(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except DashboardPublishValidationError as exc:
        details = (
            exc.result.model_dump()
            if hasattr(exc.result, "model_dump")
            else exc.result.dict()
        )
        raise HTTPException(status_code=422, detail=details) from exc


@router.get(
    "/dashboards/{dashboard_id}/publications",
    response_model=Result[List[DashboardShareRecord]],
)
def list_dashboard_publications(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(service.list_publications(dashboard_id, _user_id(user)))
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.post(
    "/dashboards/{dashboard_id}/publications/{published_revision}/rotate",
    response_model=Result[DashboardPublishResponse],
)
def rotate_dashboard_publication(
    dashboard_id: str,
    published_revision: int,
    request: DashboardShareRotateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.rotate_publication(
                dashboard_id,
                published_revision,
                _user_id(user),
                share_expires_in_seconds=request.share_expires_in_seconds,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.delete(
    "/dashboards/{dashboard_id}/publications/{published_revision}",
    response_model=Result[bool],
)
def revoke_dashboard_publication(
    dashboard_id: str,
    published_revision: int,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.revoke_publication(dashboard_id, published_revision, _user_id(user))
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get(
    "/dashboards/{dashboard_id}/permissions",
    response_model=Result[DashboardPermissionRecord],
)
def get_dashboard_permissions(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(service.get_permissions(dashboard_id, _user_id(user)))
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get(
    "/dashboards/{dashboard_id}/members",
    response_model=Result[List[DashboardMemberRecord]],
)
def list_dashboard_members(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(service.list_members(dashboard_id, _user_id(user)))
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.put(
    "/dashboards/{dashboard_id}/members/{principal_id}",
    response_model=Result[DashboardMemberRecord],
)
def upsert_dashboard_member(
    dashboard_id: str,
    principal_id: str,
    request: DashboardMemberUpsertRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    if request.principal_id != principal_id:
        raise HTTPException(
            status_code=422,
            detail="The member principal in the URL and body must match.",
        )
    try:
        return Result.succ(
            service.upsert_member(
                dashboard_id,
                _user_id(user),
                principal_id,
                request.role,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/dashboards/{dashboard_id}/members/{principal_id}",
    response_model=Result[bool],
)
def remove_dashboard_member(
    dashboard_id: str,
    principal_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.remove_member(dashboard_id, _user_id(user), principal_id)
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/dashboards/{dashboard_id}/audit",
    response_model=Result[List[DashboardAuditRecord]],
)
def list_dashboard_audit(
    dashboard_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            service.list_audit(
                dashboard_id,
                _user_id(user),
                limit=limit,
                offset=offset,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get("/dashboards/{dashboard_id}/scheduler-status")
def dashboard_scheduler_status(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    try:
        service.require_permission(
            dashboard_id, _user_id(user), DashboardAction.MANAGE_SCHEDULE
        )
        return Result.succ(scheduled_service.execution_status())
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


async def _dashboard_schedule_or_404(
    scheduled_service: ScheduledTaskService,
    schedule_id: str,
    dashboard_id: str,
    owner_id: str,
) -> TaskResponse:
    task = await scheduled_service.get_task(schedule_id, owner_id=owner_id)
    if (
        task is None
        or task.task_type != "dashboard_refresh"
        or not isinstance(task.payload, DashboardRefreshPayload)
        or task.payload.dashboard_id != dashboard_id
    ):
        raise HTTPException(status_code=404, detail="Dashboard schedule not found")
    return task


@router.post(
    "/dashboards/{dashboard_id}/schedules",
    response_model=Result[TaskResponse],
)
async def create_dashboard_schedule(
    dashboard_id: str,
    request: DashboardScheduleCreateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    actor_id = _user_id(user)
    try:
        service.require_permission(
            dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
        task = await scheduled_service.create_task(
            CreateTaskRequest(
                task_name=request.task_name,
                description=request.description,
                task_type="dashboard_refresh",
                cron_expression=request.cron_expression,
                payload=DashboardRefreshPayload(
                    dashboard_id=dashboard_id,
                    filters=request.filters,
                    publish_after_refresh=request.publish_after_refresh,
                    timeout_seconds=request.timeout_seconds,
                    max_attempts=request.max_attempts,
                ),
                creator_name=user.nick_name or user.real_name or actor_id,
            ),
            user_name=user.nick_name or user.real_name or actor_id,
            owner_id=actor_id,
        )
        service.record_audit(
            dashboard_id,
            actor_id,
            "schedule.created",
            target_type="schedule",
            target_id=task.task_id,
            details={
                "cron_expression": request.cron_expression,
                "publish_after_refresh": request.publish_after_refresh,
            },
        )
        return Result.succ(task)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/dashboards/{dashboard_id}/schedules",
    response_model=Result[List[TaskResponse]],
)
async def list_dashboard_schedules(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    actor_id = _user_id(user)
    try:
        service.require_permission(
            dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
        tasks = await scheduled_service.list_tasks(
            owner_id=actor_id,
            task_type="dashboard_refresh",
            resource_type="dashboard",
            resource_id=dashboard_id,
        )
        return Result.succ(tasks)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.put(
    "/dashboards/{dashboard_id}/schedules/{schedule_id}",
    response_model=Result[TaskResponse],
)
async def update_dashboard_schedule(
    dashboard_id: str,
    schedule_id: str,
    request: DashboardScheduleUpdateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    actor_id = _user_id(user)
    try:
        service.require_permission(
            dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
        await _dashboard_schedule_or_404(
            scheduled_service, schedule_id, dashboard_id, actor_id
        )
        task = await scheduled_service.update_task(
            schedule_id,
            UpdateTaskRequest(**model_dump_compat(request, by_alias=False)),
            owner_id=actor_id,
        )
        service.record_audit(
            dashboard_id,
            actor_id,
            "schedule.updated",
            target_type="schedule",
            target_id=schedule_id,
        )
        return Result.succ(task)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/dashboards/{dashboard_id}/schedules/{schedule_id}/toggle",
    response_model=Result[TaskResponse],
)
async def toggle_dashboard_schedule(
    dashboard_id: str,
    schedule_id: str,
    request: DashboardScheduleToggleRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    actor_id = _user_id(user)
    try:
        service.require_permission(
            dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
        await _dashboard_schedule_or_404(
            scheduled_service, schedule_id, dashboard_id, actor_id
        )
        task = await scheduled_service.toggle_task(
            schedule_id, request.enabled, owner_id=actor_id
        )
        service.record_audit(
            dashboard_id,
            actor_id,
            "schedule.toggled",
            target_type="schedule",
            target_id=schedule_id,
            details={"enabled": request.enabled},
        )
        return Result.succ(task)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete(
    "/dashboards/{dashboard_id}/schedules/{schedule_id}",
    response_model=Result[bool],
)
async def delete_dashboard_schedule(
    dashboard_id: str,
    schedule_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    actor_id = _user_id(user)
    try:
        service.require_permission(
            dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
        await _dashboard_schedule_or_404(
            scheduled_service, schedule_id, dashboard_id, actor_id
        )
        await scheduled_service.delete_task(schedule_id, owner_id=actor_id)
        service.record_audit(
            dashboard_id,
            actor_id,
            "schedule.deleted",
            target_type="schedule",
            target_id=schedule_id,
        )
        return Result.succ(True)
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/dashboards/{dashboard_id}/schedules/{schedule_id}/run",
    response_model=Result[RunResponse],
)
async def run_dashboard_schedule_now(
    dashboard_id: str,
    schedule_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    actor_id = _user_id(user)
    try:
        service.require_permission(
            dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
        await _dashboard_schedule_or_404(
            scheduled_service, schedule_id, dashboard_id, actor_id
        )
        # "Paused" controls future automatic runs. It must not prevent an
        # authenticated owner from explicitly choosing "Run now".
        executed = await run_scheduled_task(schedule_id, allow_disabled=True)
        if not executed:
            raise HTTPException(status_code=409, detail="Schedule is already running")
        runs = await scheduled_service.list_runs(
            schedule_id, limit=1, owner_id=actor_id
        )
        if not runs:
            raise HTTPException(status_code=500, detail="Schedule run was not recorded")
        service.record_audit(
            dashboard_id,
            actor_id,
            "schedule.executed",
            target_type="schedule",
            target_id=schedule_id,
            details={"run_id": runs[0].run_id, "status": runs[0].status},
        )
        return Result.succ(runs[0])
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get(
    "/dashboards/{dashboard_id}/schedules/{schedule_id}/runs",
    response_model=Result[List[RunResponse]],
)
async def list_dashboard_schedule_runs(
    dashboard_id: str,
    schedule_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
    scheduled_service: ScheduledTaskService = Depends(get_scheduled_task_service),
):
    actor_id = _user_id(user)
    try:
        service.require_permission(
            dashboard_id, actor_id, DashboardAction.MANAGE_SCHEDULE
        )
        await _dashboard_schedule_or_404(
            scheduled_service, schedule_id, dashboard_id, actor_id
        )
        return Result.succ(
            await scheduled_service.list_runs(
                schedule_id,
                limit=limit,
                offset=offset,
                owner_id=actor_id,
            )
        )
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc


@router.get(
    "/public/dashboards/{token}", response_model=Result[PublicDashboardSnapshot]
)
def get_public_dashboard(
    token: str, service: DashboardService = Depends(get_dashboard_service)
):
    """Read a fixed snapshot or refresh data through an explicit live-share grant."""

    try:
        if token.startswith("live_"):
            return Result.succ(LiveShareService(service).read(token))
        return Result.succ(service.get_public_snapshot(token))
    except DashboardAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="分享已失效") from exc
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/public/dashboards/{token}/filter",
    response_model=Result[PublicDashboardFilterResponse],
)
def filter_public_dashboard(
    token: str,
    request: PublicDashboardFilterRequest,
    service: DashboardService = Depends(get_dashboard_service),
):
    """Filter bounded publication data; only live grants may renew the dataset."""

    try:
        if token.startswith("live_"):
            result = LiveShareService(service).read(token, request.filters)
            return Result.succ(
                PublicDashboardFilterResponse(
                    snapshot=result.snapshot,
                    stale=result.stale,
                    refresh_error=result.refresh_error,
                )
            )
        return Result.succ(service.filter_public_snapshot(token, request.filters))
    except DashboardAccessDeniedError as exc:
        raise HTTPException(status_code=404, detail="分享已失效") from exc
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardPublicationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class FolderNameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/dashboards/{dashboard_id}/cover")
def read_dashboard_cover(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: CoverService(service).read(dashboard_id, _user_id(user))
    )


@router.put("/dashboards/{dashboard_id}/cover")
def save_dashboard_cover(
    dashboard_id: str,
    request: DashboardCoverRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return _feedback_call(
            lambda: CoverService(service).save(dashboard_id, _user_id(user), request)
        )
    except DashboardConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


class CatalogGenerateRequest(BaseModel):
    data_source_id: str = Field(min_length=1, max_length=255)
    mapping: Optional[TemplateSourceMapping] = None
    schema_payload: Optional[DashboardSchemaV1] = Field(default=None, alias="schema")


@router.get("/dashboard-catalog/{template_id}/features")
def inspect_catalog_features(template_id: str):
    return _feedback_call(lambda: template_features(template_id))


@router.post("/dashboard-catalog/{template_id}/adapt")
async def adapt_catalog_dashboard(
    template_id: str,
    request: TemplateAdaptRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    try:
        return Result.succ(
            await adapt_template(service, template_id, _user_id(user), request)
        )
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except (ValueError, DashboardSchemaValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="AI 适配超时，请重试。") from exc


@router.get("/dashboard-catalog/{template_id}/source")
def inspect_catalog_source(
    template_id: str,
    data_source_id: str = Query(min_length=1, max_length=255),
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: inspect_source(
            service, data_source_id, _user_id(user), template_id, allow_any_dialect=True
        )
    )


@router.post("/dashboard-catalog/{template_id}/preview")
def preview_catalog_dashboard(
    template_id: str,
    request: CatalogGenerateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: preview_template(
            service,
            template_id,
            request.data_source_id,
            _user_id(user),
            request.mapping,
        )
    )


@router.post(
    "/dashboard-catalog/{template_id}/generate", response_model=Result[DashboardRecord]
)
def generate_catalog_dashboard(
    template_id: str,
    request: CatalogGenerateRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    if request.schema_payload is not None:
        return _feedback_call(
            lambda: create_adapted_template(
                service,
                template_id,
                request.data_source_id,
                _user_id(user),
                request.schema_payload,
            )
        )
    return _feedback_call(
        lambda: instantiate_template(
            service,
            template_id,
            request.data_source_id,
            _user_id(user),
            request.mapping,
        )
    )


class FolderMoveRequest(BaseModel):
    folder_id: Optional[str] = Field(default=None, max_length=64)


def _feedback_call(operation):
    try:
        return Result.succ(operation())
    except DashboardNotFoundError as exc:
        raise _not_found(exc) from exc
    except DashboardAccessDeniedError as exc:
        raise _forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/dashboard-folders")
def list_folders(
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(lambda: FolderService(service).list(_user_id(user)))


@router.post("/dashboard-folders")
def create_folder(
    request: FolderNameRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: FolderService(service).save(_user_id(user), request.name)
    )


@router.put("/dashboard-folders/{folder_id}")
def rename_folder(
    folder_id: str,
    request: FolderNameRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: FolderService(service).save(_user_id(user), request.name, folder_id)
    )


@router.delete("/dashboard-folders/{folder_id}")
def delete_folder(
    folder_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: FolderService(service).delete(_user_id(user), folder_id)
    )


@router.put("/dashboards/{dashboard_id}/folder")
def move_to_folder(
    dashboard_id: str,
    request: FolderMoveRequest,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: FolderService(service).move(
            _user_id(user), dashboard_id, request.folder_id
        )
    )


@router.post("/dashboards/{dashboard_id}/live-share")
def create_live_share(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: LiveShareService(service).create(dashboard_id, _user_id(user))
    )


@router.get("/dashboards/{dashboard_id}/live-share")
def live_share_status(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: LiveShareService(service).status(dashboard_id, _user_id(user))
    )


@router.delete("/dashboards/{dashboard_id}/live-share")
def revoke_live_share(
    dashboard_id: str,
    user: UserRequest = Depends(get_user_from_headers),
    service: DashboardService = Depends(get_dashboard_service),
):
    return _feedback_call(
        lambda: LiveShareService(service).revoke(dashboard_id, _user_id(user))
    )
