"""Agent observability read-side protocol and default implementation.

This package defines a backend-agnostic observability protocol
(`ObservabilityProvider`) that the product UI talks to. Concrete backends
(default SQLite, ZizkaDB, future OTel/Prometheus) implement the protocol; the
dashboard never knows which one is active. Select the backend via the dotted-path
config `observability_provider_cls` (mirrors `tracer_storage_cls`).
"""

from dbgpt.observability.base import ObservabilityProvider
from dbgpt.observability.capability import Capability
from dbgpt.observability.default_provider import DefaultObservabilityProvider
from dbgpt.observability.models import (
    AgentStats,
    AgentSummary,
    CausalChain,
    DriftReport,
    EventHit,
    Granularity,
    HealthRow,
    MemoryContext,
    Metric,
    MetricFilter,
    SessionDiff,
    SessionSummary,
    SpanNode,
    Timeseries,
    TimeseriesPoint,
    TimeWindow,
    TraceFilter,
    TraceSummary,
    TraceTree,
)

__all__ = [
    "ObservabilityProvider",
    "DefaultObservabilityProvider",
    "Capability",
    "Metric",
    "Granularity",
    "TimeWindow",
    "MetricFilter",
    "Timeseries",
    "TimeseriesPoint",
    "TraceFilter",
    "TraceSummary",
    "TraceTree",
    "SpanNode",
    "AgentSummary",
    "AgentStats",
    "HealthRow",
    "SessionSummary",
    "SessionDiff",
    "DriftReport",
    "EventHit",
    "MemoryContext",
    "CausalChain",
]
