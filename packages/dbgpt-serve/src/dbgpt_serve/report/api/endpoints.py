"""Owner-aware HTTP transport for persisted reports and evidence."""

from typing import Callable, List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request

from dbgpt.component import SystemApp
from dbgpt_serve.core import Result
from dbgpt_serve.utils.auth import UserRequest, get_user_from_headers

from ..domain import ReportWriteConflictError
from ..models.models import MAX_OWNER_ID_LENGTH
from ..rendering import REPORT_PREVIEW_CSP, render_report_html
from ..service import (
    ReportBlockNotFoundError,
    ReportNotFoundError,
    ReportService,
)
from .schemas import (
    RenderObservationRequest,
    ReportEvidenceResponse,
    ReportRunResponse,
    ReportRunSummaryResponse,
    SaveReportRequest,
)


class ReportApiError(Exception):
    """Transport error with stable status and machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class _ReportApiRoute(APIRoute):
    def get_route_handler(self):
        original_handler = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original_handler(request)
            except ReportApiError as error:
                return JSONResponse(
                    status_code=error.status_code,
                    content=Result.failed(
                        msg=error.message, err_code=error.code
                    ).to_dict(),
                )

        return handler


router = APIRouter(route_class=_ReportApiRoute)
global_system_app: Optional[SystemApp] = None
_service_instance: Optional[ReportService] = None


def init_endpoints(system_app: SystemApp, service: ReportService) -> None:
    """Bind the lifecycle-owned service used by FastAPI dependencies."""
    global global_system_app, _service_instance
    global_system_app = system_app
    _service_instance = service


def _reset_endpoints() -> None:
    """Fail closed after lifecycle shutdown and isolate endpoint tests."""
    global global_system_app, _service_instance
    global_system_app = None
    _service_instance = None


def get_report_service() -> ReportService:
    if _service_instance is None:
        raise ReportApiError(
            503,
            "REPORT_SERVICE_UNAVAILABLE",
            "Report persistence is not available.",
        )
    return _service_instance


def get_authenticated_owner(
    user: UserRequest = Depends(get_user_from_headers),
) -> str:
    """Resolve owner from DB-GPT authentication, never from request bodies."""
    owner_id = user.user_id.strip() if user and user.user_id else ""
    if not owner_id:
        raise ReportApiError(401, "REPORT_OWNER_REQUIRED", "An owner is required.")
    if len(owner_id) > MAX_OWNER_ID_LENGTH:
        raise ReportApiError(401, "REPORT_OWNER_INVALID", "The owner is invalid.")
    return owner_id


async def _call_service(function: Callable, *args, **kwargs):
    try:
        return await run_in_threadpool(function, *args, **kwargs)
    except ReportBlockNotFoundError as error:
        raise ReportApiError(
            404, "REPORT_BLOCK_NOT_FOUND", "Report block not found."
        ) from error
    except ReportNotFoundError as error:
        raise ReportApiError(404, "REPORT_NOT_FOUND", "Report not found.") from error
    except ReportWriteConflictError as error:
        raise ReportApiError(
            409,
            "REPORT_WRITE_CONFLICT",
            "The report changed concurrently; retry the request.",
        ) from error
    except ValueError as error:
        raise ReportApiError(400, "REPORT_INVALID", str(error)) from error


@router.get("/{report_id}/runs/{run_id}/artifacts/{artifact_id}/content")
async def download_artifact_content(
    report_id: str,
    run_id: str,
    artifact_id: str,
    part: Literal[
        "result", "output", "source", "renderer_template", "streams"
    ] = "result",
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    path, media_type = await _call_service(
        service.artifact_content, owner_id, report_id, run_id, artifact_id, part
    )
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.post("/{report_id}/runs/{run_id}/render-observations")
async def save_render_observation(
    report_id: str,
    run_id: str,
    request: RenderObservationRequest,
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    observation = await _call_service(
        service.save_render_observation,
        owner_id,
        report_id,
        run_id,
        request.model_dump(exclude_none=True),
    )
    return Result.succ(observation)


@router.get("/{report_id}/runs/{run_id}/render-observations")
async def get_render_observations(
    report_id: str,
    run_id: str,
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    return Result.succ(
        await _call_service(
            service.list_render_observations, owner_id, report_id, run_id
        )
    )


@router.get(
    "/{report_id}/runs/{run_id}/render-observations/{artifact_id}/{observation_id}/content"
)
async def download_render_options(
    report_id: str,
    run_id: str,
    artifact_id: str,
    observation_id: str,
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    path, media_type = await _call_service(
        service.render_observation_content,
        owner_id,
        report_id,
        run_id,
        artifact_id,
        observation_id,
    )
    return FileResponse(path, media_type=media_type, filename="render-options.json")


@router.post("/", response_model=Result[ReportRunResponse])
async def save_report(
    request: SaveReportRequest,
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    """Persist a validated protocol document as a new immutable revision."""
    record = await _call_service(
        service.save,
        owner_id=owner_id,
        document=request.document,
        trigger_type=request.trigger_type,
        parent_run_id=request.parent_run_id,
    )
    return Result.succ(ReportRunResponse.from_record(record))


@router.get("/{report_id}", response_model=Result[ReportRunResponse])
async def get_latest_report(
    report_id: str,
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    """Read the latest visible report revision."""
    record = await _call_service(service.get_latest, owner_id, report_id)
    return Result.succ(ReportRunResponse.from_record(record))


@router.get("/{report_id}/runs", response_model=Result[List[ReportRunSummaryResponse]])
async def list_report_runs(
    report_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    """List immutable report revisions newest first."""
    runs = await _call_service(
        service.list_runs, owner_id, report_id, limit=limit, offset=offset
    )
    return Result.succ([ReportRunSummaryResponse.from_domain(run) for run in runs])


@router.get("/{report_id}/runs/{run_id}", response_model=Result[ReportRunResponse])
async def get_report_run(
    report_id: str,
    run_id: str,
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    """Read one exact immutable report revision."""
    record = await _call_service(service.get_run, owner_id, report_id, run_id)
    return Result.succ(ReportRunResponse.from_record(record))


@router.get(
    "/{report_id}/runs/{run_id}/preview",
    response_class=HTMLResponse,
)
async def preview_report_run(
    report_id: str,
    run_id: str,
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    """Render one owner-scoped immutable revision as script-free HTML."""
    record = await _call_service(service.get_run, owner_id, report_id, run_id)
    return HTMLResponse(
        render_report_html(record.document),
        headers={
            "Content-Security-Policy": REPORT_PREVIEW_CSP,
            "Content-Disposition": "inline",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/{report_id}/runs/{run_id}/blocks/{block_id}/evidence",
    response_model=Result[List[ReportEvidenceResponse]],
)
async def get_report_block_evidence(
    report_id: str,
    run_id: str,
    block_id: str,
    limit: int = Query(50, ge=1, le=200),
    owner_id: str = Depends(get_authenticated_owner),
    service: ReportService = Depends(get_report_service),
):
    """Read ordered evidence bindings and their referenced artifacts."""
    details = await _call_service(
        service.get_block_evidence,
        owner_id,
        report_id,
        run_id,
        block_id,
        limit=limit,
    )
    return Result.succ([ReportEvidenceResponse.from_domain(item) for item in details])


__all__ = ["init_endpoints", "router"]
