"""REST API endpoints for the finance research module."""

import logging
from functools import cache
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer

from dbgpt.component import SystemApp

from ..config import ServeConfig
from ..service.service import Service
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    BreakdownRecord,
    Citation,
    CompareRequest,
    CompareResponse,
    MetricItem,
)

router = APIRouter()

global_system_app: Optional[SystemApp] = None

get_bearer_token = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


def get_service() -> Service:
    """Return the finance service instance."""
    return Service.get_instance(global_system_app)


@cache
def _parse_api_keys(api_keys: str) -> List[str]:
    """Parse the string api keys to a list."""
    if not api_keys:
        return []
    return [key.strip() for key in api_keys.split(",")]


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    service: Service = Depends(get_service),
) -> Optional[str]:
    """Reject requests without a valid bearer token when api_keys are set."""
    if service.config.api_keys:
        api_keys = _parse_api_keys(service.config.api_keys)
        if auth is None or (token := auth.credentials) not in api_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )
        return token
    # api_keys not set; allow all
    return None


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints and register the service component."""
    global global_system_app
    global_system_app = system_app
    system_app.register(Service, config=config)


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "finance"}


def _build_response(result: dict) -> AnalyzeResponse:
    citations = [Citation(**c) for c in result["citations"]]
    metrics = [MetricItem(**m) for m in result.get("metrics", [])]
    segments = [BreakdownRecord(**r) for r in result.get("segments", [])]
    regions = [BreakdownRecord(**r) for r in result.get("regions", [])]
    return AnalyzeResponse(
        company=result["company"],
        report=result["report"],
        metrics=metrics,
        segments=segments,
        regions=regions,
        citations=citations,
    )


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    dependencies=[Depends(check_api_key)],
)
async def analyze(request: AnalyzeRequest):
    """Analyze a company's public financial reports and return a cited report."""
    result = await run_in_threadpool(
        get_service().analyze_company, request.company, request.query
    )
    return _build_response(result)


@router.post(
    "/analyze/upload",
    response_model=AnalyzeResponse,
    dependencies=[Depends(check_api_key)],
)
async def analyze_with_files(
    company: str = Form(..., description="Company name to analyze."),
    query: Optional[str] = Form(None),
    files: List[UploadFile] = File(default_factory=list),
):
    """Analyze a company using discovered public sources plus uploaded files."""
    _MAX_FILES = 5
    _MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB per file
    _MAX_TOTAL_BYTES = 50 * 1024 * 1024  # 50 MB per request

    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=400, detail=f"too many files: maximum {_MAX_FILES}"
        )
    uploaded = []
    total = 0
    for f in files:
        data = await f.read()
        if len(data) > _MAX_FILE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"file {f.filename} exceeds {_MAX_FILE_BYTES} bytes",
            )
        total += len(data)
        if total > _MAX_TOTAL_BYTES:
            raise HTTPException(
                status_code=400, detail="total upload size exceeds limit"
            )
        uploaded.append({"filename": f.filename or "upload", "data": data})
    result = await run_in_threadpool(
        get_service().analyze_company, company, query, uploaded
    )
    return _build_response(result)


@router.post(
    "/compare",
    response_model=CompareResponse,
    dependencies=[Depends(check_api_key)],
)
async def compare(request: CompareRequest):
    """Compare multiple companies' financials."""
    result = await run_in_threadpool(
        get_service().compare_companies, request.companies, request.queries
    )
    metrics = {
        company: [MetricItem(**m) for m in items]
        for company, items in result.get("metrics", {}).items()
    }
    return CompareResponse(
        companies=result["companies"],
        report=result["report"],
        comparison=result.get("comparison", []),
        metrics=metrics,
    )
