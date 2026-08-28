"""DTOs for the observability protocol.

These dataclasses are the wire format between `ObservabilityProvider`
implementations and the `observability_serve` HTTP layer. Backend implementations
translate their native structures into these DTOs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class Metric(str, Enum):
    """Metrics supported by `ObservabilityProvider.get_metrics`."""

    EVENT_VOLUME = "event_volume"
    REQUEST_RATE = "request_rate"
    ERROR_RATE = "error_rate"
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    TOKEN_RATE = "token_rate"
    COST_RATE = "cost_rate"


class Granularity(str, Enum):
    """Time bucket granularity for time-series."""

    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


@dataclass
class TimeWindow:
    start: datetime
    end: datetime
    granularity: Granularity = Granularity.HOUR


@dataclass
class MetricFilter:
    agent_name: Optional[str] = None
    model_name: Optional[str] = None
    conversation_id: Optional[str] = None
    status: Optional[str] = None


@dataclass
class TimeseriesPoint:
    timestamp: datetime
    value: float


@dataclass
class Timeseries:
    metric: Metric
    points: List[TimeseriesPoint] = field(default_factory=list)


@dataclass
class TraceFilter:
    trace_id: Optional[str] = None
    agent_name: Optional[str] = None
    model_name: Optional[str] = None
    conversation_id: Optional[str] = None
    operation_name: Optional[str] = None
    status: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    # Drop pure-HTTP middleware traces (single-span `DB-GPT-Webserver` records)
    # from the list by setting a minimum span count.
    min_span_count: Optional[int] = None
    limit: int = 50
    offset: int = 0


@dataclass
class AgentSummary:
    agent_name: str
    event_count: int
    session_count: int = 0
    error_rate: float = 0.0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    drift_verdict: Optional[str] = None


@dataclass
class AgentStats:
    agent_name: str
    total_events: int
    total_sessions: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    top_operations: Dict[str, int] = field(default_factory=dict)
    error_rate: float = 0.0
    drift: Optional["DriftReport"] = None


@dataclass
class HealthRow:
    agent_name: str
    event_count: int
    error_rate: float
    drift_verdict: Optional[str] = None
    drift_score: Optional[float] = None


@dataclass
class SpanNode:
    span_id: str
    parent_span_id: Optional[str] = None
    operation_name: Optional[str] = None
    span_type: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    agent_name: Optional[str] = None
    model_name: Optional[str] = None
    tool_name: Optional[str] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[Any] = None
    children: List["SpanNode"] = field(default_factory=list)


@dataclass
class TraceTree:
    trace_id: str
    root: Optional[SpanNode] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    span_count: int = 0
    status: Optional[str] = None
    conversation_id: Optional[str] = None


@dataclass
class TraceSummary:
    trace_id: str
    root_operation_name: Optional[str] = None
    agent_name: Optional[str] = None
    start_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    span_count: int = 0
    model_name: Optional[str] = None
    total_tokens: Optional[int] = None
    cost: Optional[float] = None
    conversation_id: Optional[str] = None


@dataclass
class SessionSummary:
    session_id: str
    agent_name: Optional[str] = None
    event_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_count: int = 0
    new_event_types: Optional[List[str]] = None


@dataclass
class ModelUsageSummary:
    """Per-model token / call / latency aggregation (AntCC-style token panel)."""

    model_name: str
    call_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_hit_tokens: int = 0
    cache_miss_tokens: int = 0
    avg_duration_ms: Optional[float] = None
    error_count: int = 0


@dataclass
class SessionDiff:
    session_id: str
    event_type_diff: Dict[str, Any] = field(default_factory=dict)
    new_event_types: List[str] = field(default_factory=list)
    causal_depth: int = 0


@dataclass
class DriftReport:
    agent_name: str
    score: float
    verdict: str  # stable / minor_drift / noticeable_drift / significant_drift
    biggest_changes: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class EventHit:
    event_id: str
    event_type: Optional[str] = None
    agent_name: Optional[str] = None
    timestamp: Optional[datetime] = None
    score: Optional[float] = None
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CausalChain:
    root_event_id: Optional[str] = None
    depth: int = 0
    chain: List[EventHit] = field(default_factory=list)


@dataclass
class MemoryContext:
    context: str = ""
    token_count: int = 0
    sources: List[EventHit] = field(default_factory=list)
