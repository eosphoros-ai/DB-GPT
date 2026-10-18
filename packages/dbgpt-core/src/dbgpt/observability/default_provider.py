"""Default observability backend — reads the isolated SQLite span store.

Capabilities: ``TRACES`` and ``METRICS`` only (no drift / semantic / memory —
those require the ZizkaDB backend). The default backend lets Observability work
out of the box with zero external dependencies.

Metric computation:
  * rate / volume / token / cost / error-rate → SQL ``GROUP BY strftime`` time
    bucket (efficient).
  * latency p50 / p95 / p99 → durations are loaded per window and percentiles
    computed in Python (SQLite lacks ``percentile_cont``).
"""

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import case, func

from dbgpt.observability.base import ObservabilityProvider
from dbgpt.observability.capability import Capability
from dbgpt.observability.models import (
    AgentStats,
    AgentSummary,
    Granularity,
    HealthRow,
    Metric,
    MetricFilter,
    ModelUsageSummary,
    SessionSummary,
    SpanNode,
    Timeseries,
    TimeseriesPoint,
    TimeWindow,
    TraceFilter,
    TraceSummary,
    TraceTree,
)
from dbgpt.observability.span_store import (
    ObservabilitySpanEntity,
    get_observability_store,
)

logger = logging.getLogger(__name__)


def _percentile(values: List[float], percentile: float) -> float:
    """Percentile via nearest-rank (p in 0..100). Returns 0.0 for empty input."""
    if not values:
        return 0.0
    ordered = sorted(v for v in values if v is not None)
    if not ordered:
        return 0.0
    rank = math.ceil(percentile / 100.0 * len(ordered))
    idx = max(0, min(rank - 1, len(ordered) - 1))
    return float(ordered[idx])


_BUCKETS = {
    Granularity.MINUTE: ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M"),
    Granularity.HOUR: ("%Y-%m-%d %H", "%Y-%m-%d %H"),
    Granularity.DAY: ("%Y-%m-%d", "%Y-%m-%d"),
}


class DefaultObservabilityProvider(ObservabilityProvider):
    """Reads spans from the isolated observability SQLite file."""

    capabilities = {Capability.TRACES, Capability.METRICS}

    def __init__(self, sqlite_path: Optional[str] = None):
        super().__init__()
        self._sqlite_path = sqlite_path

    @property
    def _session(self):
        _, factory = get_observability_store(self._sqlite_path)
        return factory()

    # ---- agents ----
    def list_agents(
        self, time_from: Optional[datetime] = None, time_to: Optional[datetime] = None
    ) -> List[AgentSummary]:
        with self._session as session:
            q = session.query(
                ObservabilitySpanEntity.agent_name,
                func.count().label("events"),
                func.count(ObservabilitySpanEntity.conversation_id.distinct()).label(
                    "sessions"
                ),
                func.max(ObservabilitySpanEntity.start_time).label("last_seen"),
                func.min(ObservabilitySpanEntity.start_time).label("first_seen"),
            ).filter(ObservabilitySpanEntity.agent_name.isnot(None))
            if time_from:
                q = q.filter(ObservabilitySpanEntity.start_time >= time_from)
            if time_to:
                q = q.filter(ObservabilitySpanEntity.start_time <= time_to)
            rows = q.group_by(ObservabilitySpanEntity.agent_name).all()
            return [
                AgentSummary(
                    agent_name=r.agent_name,
                    event_count=int(r.events or 0),
                    session_count=int(r.sessions or 0),
                    last_seen=r.last_seen,
                    first_seen=r.first_seen,
                )
                for r in rows
            ]

    def agent_stats(self, agent_name: str) -> AgentStats:
        with self._session as session:
            rows = (
                session.query(ObservabilitySpanEntity)
                .filter(ObservabilitySpanEntity.agent_name == agent_name)
                .all()
            )
            total = len(rows)
            top_ops: Dict[str, int] = {}
            errors = 0
            for r in rows:
                op = r.operation_name or "unknown"
                top_ops[op] = top_ops.get(op, 0) + 1
                if r.status == "ERROR":
                    errors += 1
            top_ops = dict(
                sorted(top_ops.items(), key=lambda kv: kv[1], reverse=True)[:10]
            )
            return AgentStats(
                agent_name=agent_name,
                total_events=total,
                total_sessions=len(
                    {r.conversation_id for r in rows if r.conversation_id}
                ),
                first_seen=min(
                    (r.start_time for r in rows if r.start_time), default=None
                ),
                last_seen=max(
                    (r.start_time for r in rows if r.start_time), default=None
                ),
                top_operations=top_ops,
                error_rate=(errors / total) if total else 0.0,
            )

    def agent_health_matrix(
        self, time_from: Optional[datetime] = None, time_to: Optional[datetime] = None
    ) -> List[HealthRow]:
        with self._session as session:
            q = session.query(
                ObservabilitySpanEntity.agent_name,
                func.count().label("events"),
                func.sum(
                    case(
                        (ObservabilitySpanEntity.status == "ERROR", 1),
                        else_=0,
                    )
                ).label("errors"),
            ).filter(ObservabilitySpanEntity.agent_name.isnot(None))
            if time_from:
                q = q.filter(ObservabilitySpanEntity.start_time >= time_from)
            if time_to:
                q = q.filter(ObservabilitySpanEntity.start_time <= time_to)
            rows = q.group_by(ObservabilitySpanEntity.agent_name).all()
            return [
                HealthRow(
                    agent_name=r.agent_name,
                    event_count=int(r.events or 0),
                    error_rate=(float(r.errors or 0) / float(r.events))
                    if r.events
                    else 0.0,
                )
                for r in rows
            ]

    # ---- traces ----
    def search_traces(self, filter: TraceFilter) -> List[TraceSummary]:
        with self._session as session:
            q = session.query(
                ObservabilitySpanEntity.trace_id,
                func.min(ObservabilitySpanEntity.start_time).label("start"),
                func.max(ObservabilitySpanEntity.end_time).label("end"),
                func.count().label("span_count"),
                func.min(ObservabilitySpanEntity.agent_name).label("agent_name"),
                func.min(ObservabilitySpanEntity.conversation_id).label("conv"),
                func.min(ObservabilitySpanEntity.model_name).label("model"),
                func.sum(ObservabilitySpanEntity.total_tokens).label("tokens"),
                func.sum(ObservabilitySpanEntity.cost).label("cost"),
                case(
                    (
                        func.sum(
                            case(
                                (ObservabilitySpanEntity.status == "ERROR", 1),
                                else_=0,
                            )
                        )
                        > 0,
                        "ERROR",
                    ),
                    else_="OK",
                ).label("status"),
                func.min(ObservabilitySpanEntity.operation_name).label("root_op"),
            ).group_by(ObservabilitySpanEntity.trace_id)
            q = self._apply_trace_filter(q, filter)
            if filter.min_span_count is not None:
                q = q.having(func.count() > filter.min_span_count)
            q = q.order_by(func.min(ObservabilitySpanEntity.start_time).desc())
            q = q.limit(filter.limit).offset(filter.offset)
            rows = q.all()
            return [
                TraceSummary(
                    trace_id=r.trace_id,
                    root_operation_name=r.root_op,
                    agent_name=r.agent_name,
                    start_time=r.start,
                    duration_ms=_duration_ms(r.start, r.end),
                    status=r.status,
                    span_count=int(r.span_count or 0),
                    model_name=r.model,
                    total_tokens=int(r.tokens) if r.tokens is not None else None,
                    cost=float(r.cost) if r.cost is not None else None,
                    conversation_id=r.conv,
                )
                for r in rows
            ]

    def get_trace(self, trace_id: str) -> Optional[TraceTree]:
        with self._session as session:
            rows = (
                session.query(ObservabilitySpanEntity)
                .filter(ObservabilitySpanEntity.trace_id == trace_id)
                .order_by(ObservabilitySpanEntity.start_time.asc())
                .all()
            )
            if not rows:
                return None
            import json

            nodes: Dict[str, SpanNode] = {}
            for r in rows:
                nodes[r.span_id] = SpanNode(
                    span_id=r.span_id,
                    parent_span_id=r.parent_span_id,
                    operation_name=r.operation_name,
                    span_type=r.span_type,
                    start_time=r.start_time,
                    end_time=r.end_time,
                    duration_ms=r.duration_ms,
                    status=r.status,
                    agent_name=r.agent_name,
                    model_name=r.model_name,
                    tool_name=r.tool_name,
                    total_tokens=r.total_tokens,
                    cost=r.cost,
                    metadata=json.loads(r.metadata_json) if r.metadata_json else {},
                    error=json.loads(r.error_json) if r.error_json else None,
                )
            roots: List[SpanNode] = []
            for node in nodes.values():
                if node.parent_span_id and node.parent_span_id in nodes:
                    nodes[node.parent_span_id].children.append(node)
                else:
                    roots.append(node)
            root = roots[0] if roots else None
            starts = [r.start_time for r in rows if r.start_time]
            ends = [r.end_time for r in rows if r.end_time]
            start_time = min(starts, default=None)
            end_time = max(ends, default=None)
            status = (
                "ERROR" if any(n.status == "ERROR" for n in nodes.values()) else "OK"
            )
            conversation_id = next(
                (r.conversation_id for r in rows if r.conversation_id), None
            )
            return TraceTree(
                trace_id=trace_id,
                root=root,
                start_time=start_time,
                end_time=end_time,
                duration_ms=_duration_ms(start_time, end_time),
                span_count=len(rows),
                status=status,
                conversation_id=conversation_id,
            )

    # ---- sessions (default backend uses conversation_id as the session key) ----
    def list_sessions(
        self, agent_name: Optional[str] = None, limit: int = 50
    ) -> List[SessionSummary]:
        with self._session as session:
            q = session.query(
                ObservabilitySpanEntity.conversation_id.label("sid"),
                func.min(ObservabilitySpanEntity.agent_name).label("agent"),
                func.count().label("events"),
                func.min(ObservabilitySpanEntity.start_time).label("start"),
                func.max(ObservabilitySpanEntity.end_time).label("end"),
                func.sum(
                    case(
                        (ObservabilitySpanEntity.status == "ERROR", 1),
                        else_=0,
                    )
                ).label("errors"),
            ).filter(ObservabilitySpanEntity.conversation_id.isnot(None))
            if agent_name:
                q = q.filter(ObservabilitySpanEntity.agent_name == agent_name)
            rows = (
                q.group_by(ObservabilitySpanEntity.conversation_id)
                .order_by(func.min(ObservabilitySpanEntity.start_time).desc())
                .limit(limit)
                .all()
            )
            return [
                SessionSummary(
                    session_id=r.sid,
                    agent_name=r.agent,
                    event_count=int(r.events or 0),
                    start_time=r.start,
                    end_time=r.end,
                    duration_seconds=(
                        (r.end - r.start).total_seconds() if r.start and r.end else None
                    ),
                    error_count=int(r.errors or 0),
                )
                for r in rows
            ]

    # ---- model usage (AntCC-style token panel) ----
    def model_usage(
        self, time_from: Optional[datetime] = None, time_to: Optional[datetime] = None
    ) -> List[ModelUsageSummary]:
        with self._session as session:
            e = ObservabilitySpanEntity
            q = session.query(
                e.model_name.label("model"),
                func.count().label("calls"),
                func.sum(e.prompt_tokens).label("prompt"),
                func.sum(e.completion_tokens).label("completion"),
                func.sum(e.total_tokens).label("total"),
                func.sum(e.cache_hit_tokens).label("cache_hit"),
                func.sum(e.cache_miss_tokens).label("cache_miss"),
                func.avg(e.duration_ms).label("avg_ms"),
                func.sum(case((e.status == "ERROR", 1), else_=0)).label("errors"),
            ).filter(e.model_name.isnot(None))
            if time_from:
                q = q.filter(e.start_time >= time_from)
            if time_to:
                q = q.filter(e.start_time <= time_to)
            rows = (
                q.group_by(e.model_name).order_by(func.sum(e.total_tokens).desc()).all()
            )
            return [
                ModelUsageSummary(
                    model_name=r.model,
                    call_count=int(r.calls or 0),
                    prompt_tokens=int(r.prompt or 0),
                    completion_tokens=int(r.completion or 0),
                    total_tokens=int(r.total or 0),
                    cache_hit_tokens=int(r.cache_hit or 0),
                    cache_miss_tokens=int(r.cache_miss or 0),
                    avg_duration_ms=float(r.avg_ms) if r.avg_ms is not None else None,
                    error_count=int(r.errors or 0),
                )
                for r in rows
            ]

    # ---- metrics ----
    def get_metrics(
        self,
        metric: Metric,
        window: TimeWindow,
        filter: Optional[MetricFilter] = None,
    ) -> Timeseries:
        if metric in (Metric.LATENCY_P50, Metric.LATENCY_P95, Metric.LATENCY_P99):
            return self._latency_timeseries(metric, window, filter)
        return self._rate_timeseries(metric, window, filter)

    # -- internals --
    def _latency_timeseries(
        self,
        metric: Metric,
        window: TimeWindow,
        filter: Optional[MetricFilter],
    ) -> Timeseries:
        pct = {Metric.LATENCY_P50: 50, Metric.LATENCY_P95: 95, Metric.LATENCY_P99: 99}[
            metric
        ]
        sql_fmt, py_fmt = _BUCKETS[window.granularity]
        with self._session as session:
            q = session.query(
                func.strftime(sql_fmt, ObservabilitySpanEntity.start_time).label(
                    "bucket"
                ),
                ObservabilitySpanEntity.duration_ms,
            ).filter(
                ObservabilitySpanEntity.start_time >= window.start,
                ObservabilitySpanEntity.start_time <= window.end,
                ObservabilitySpanEntity.duration_ms.isnot(None),
            )
            q = self._apply_metric_filter(q, filter)
            rows = q.all()
            buckets: Dict[str, List[float]] = {}
            for r in rows:
                buckets.setdefault(r.bucket, []).append(float(r.duration_ms))
            points = []
            for label, vals in sorted(buckets.items()):
                points.append(
                    TimeseriesPoint(
                        timestamp=datetime.strptime(label, py_fmt),
                        value=_percentile(vals, pct),
                    )
                )
            return Timeseries(metric=metric, points=points)

    def _rate_timeseries(
        self,
        metric: Metric,
        window: TimeWindow,
        filter: Optional[MetricFilter],
    ) -> Timeseries:
        sql_fmt, py_fmt = _BUCKETS[window.granularity]
        entity = ObservabilitySpanEntity
        bucket = func.strftime(sql_fmt, entity.start_time).label("bucket")
        value_expr: Any = {
            Metric.EVENT_VOLUME: func.count(),
            Metric.REQUEST_RATE: func.count(entity.trace_id.distinct()),
            Metric.TOKEN_RATE: func.sum(entity.total_tokens),
            Metric.COST_RATE: func.sum(entity.cost),
            Metric.ERROR_RATE: func.sum(case((entity.status == "ERROR", 1), else_=0))
            * 1.0
            / func.count(),
        }[metric]
        with self._session as session:
            q = session.query(bucket, value_expr.label("value")).filter(
                entity.start_time >= window.start,
                entity.start_time <= window.end,
            )
            q = self._apply_metric_filter(q, filter)
            rows = q.group_by(bucket).order_by(bucket).all()
            points = []
            for r in rows:
                points.append(
                    TimeseriesPoint(
                        timestamp=datetime.strptime(r.bucket, py_fmt),
                        value=float(r.value) if r.value is not None else 0.0,
                    )
                )
            return Timeseries(metric=metric, points=points)

    def _apply_trace_filter(self, q, filter: TraceFilter):
        entity = ObservabilitySpanEntity
        if filter.agent_name:
            q = q.filter(entity.agent_name == filter.agent_name)
        if filter.conversation_id:
            q = q.filter(entity.conversation_id == filter.conversation_id)
        if filter.model_name:
            q = q.filter(entity.model_name == filter.model_name)
        if filter.operation_name:
            q = q.filter(entity.operation_name == filter.operation_name)
        if filter.start_time:
            q = q.filter(entity.start_time >= filter.start_time)
        if filter.end_time:
            q = q.filter(entity.start_time <= filter.end_time)
        return q

    def _apply_metric_filter(self, q, filter: Optional[MetricFilter]):
        if not filter:
            return q
        entity = ObservabilitySpanEntity
        if filter.agent_name:
            q = q.filter(entity.agent_name == filter.agent_name)
        if filter.model_name:
            q = q.filter(entity.model_name == filter.model_name)
        if filter.conversation_id:
            q = q.filter(entity.conversation_id == filter.conversation_id)
        if filter.status:
            q = q.filter(entity.status == filter.status)
        return q


def _duration_ms(start: Optional[datetime], end: Optional[datetime]) -> Optional[int]:
    if not start or not end:
        return None
    return int((end - start).total_seconds() * 1000)
