"""HTTP endpoints for the observability serve.

All endpoints delegate to the active :class:`ObservabilityProvider` via the
service layer. DTOs are returned as plain dicts (via :func:`dataclasses.asdict`)
wrapped in :class:`Result`, matching the DB-GPT frontend envelope
``{data, err_code, err_msg, success}``.
"""

from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query

from dbgpt.component import SystemApp
from dbgpt.observability.models import (
    Granularity,
    Metric,
    MetricFilter,
    TimeWindow,
    TraceFilter,
)
from dbgpt_serve.core import Result

from ..config import SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..service.service import Service

router = APIRouter()

global_system_app: Optional[SystemApp] = None


def get_service() -> Service:
    """Get the observability service instance."""
    return global_system_app.get_component(SERVE_SERVICE_COMPONENT_NAME, Service)


def _dump(obj: Any) -> Any:
    """Recursively convert dataclass DTOs to JSON-serializable dicts."""
    if obj is None:
        return None
    if isinstance(obj, list):
        return [_dump(x) for x in obj]
    if isinstance(obj, (set, tuple)):
        return [_dump(x) for x in obj]
    if is_dataclass(obj):
        return asdict(obj)
    return obj


def init_endpoints(system_app: SystemApp, config: ServeConfig) -> None:
    """Initialize the endpoints (register the service component)."""
    global global_system_app
    system_app.register(Service, config=config)
    global_system_app = system_app


@router.get("/capabilities")
async def get_capabilities(service: Service = Depends(get_service)) -> Result:
    """Return the capability set of the active backend (for UI graceful degradation)."""
    return Result.succ([c.value for c in service.provider.capabilities])


@router.get("/agents")
async def list_agents(
    time_from: Optional[datetime] = Query(default=None),
    time_to: Optional[datetime] = Query(default=None),
    service: Service = Depends(get_service),
) -> Result:
    return Result.succ(_dump(service.provider.list_agents(time_from, time_to)))


@router.get("/health")
async def health_matrix(
    time_from: Optional[datetime] = Query(default=None),
    time_to: Optional[datetime] = Query(default=None),
    service: Service = Depends(get_service),
) -> Result:
    return Result.succ(_dump(service.provider.agent_health_matrix(time_from, time_to)))


@router.get("/agents/{agent_name}/stats")
async def agent_stats(
    agent_name: str, service: Service = Depends(get_service)
) -> Result:
    return Result.succ(_dump(service.provider.agent_stats(agent_name)))


@router.get("/models/usage")
async def model_usage(
    time_from: Optional[datetime] = Query(default=None),
    time_to: Optional[datetime] = Query(default=None),
    service: Service = Depends(get_service),
) -> Result:
    """Per-model token/call/latency aggregation (AntCC-style token panel)."""
    return Result.succ(_dump(service.provider.model_usage(time_from, time_to)))


@router.get("/traces")
async def search_traces(
    trace_id: Optional[str] = Query(default=None),
    agent_name: Optional[str] = Query(default=None),
    model_name: Optional[str] = Query(default=None),
    conversation_id: Optional[str] = Query(default=None),
    operation_name: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    min_span_count: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: Service = Depends(get_service),
) -> Result:
    flt = TraceFilter(
        trace_id=trace_id,
        agent_name=agent_name,
        model_name=model_name,
        conversation_id=conversation_id,
        operation_name=operation_name,
        status=status,
        start_time=start_time,
        end_time=end_time,
        min_span_count=min_span_count,
        limit=limit,
        offset=offset,
    )
    return Result.succ(_dump(service.provider.search_traces(flt)))


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str, service: Service = Depends(get_service)) -> Result:
    return Result.succ(_dump(service.provider.get_trace(trace_id)))


@router.get("/sessions")
async def list_sessions(
    agent_name: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    service: Service = Depends(get_service),
) -> Result:
    return Result.succ(_dump(service.provider.list_sessions(agent_name, limit)))


@router.get("/metrics")
async def get_metrics(
    metric: Metric = Query(...),
    start: datetime = Query(...),
    end: datetime = Query(...),
    granularity: Granularity = Query(default=Granularity.HOUR),
    agent_name: Optional[str] = Query(default=None),
    model_name: Optional[str] = Query(default=None),
    conversation_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    service: Service = Depends(get_service),
) -> Result:
    window = TimeWindow(start=start, end=end, granularity=granularity)
    flt = MetricFilter(
        agent_name=agent_name,
        model_name=model_name,
        conversation_id=conversation_id,
        status=status,
    )
    return Result.succ(_dump(service.provider.get_metrics(metric, window, flt)))
