"""The backend-agnostic observability read-side protocol.

The product UI talks only to :class:`ObservabilityProvider`; concrete backends
(default SQLite, ZizkaDB, future OTel/Prometheus) implement it. Select the active
backend via the dotted-path config ``observability_provider_cls`` (mirrors the
existing ``tracer_storage_cls`` mechanism), so swapping backends is a one-line
config change.

Each implementation declares ``capabilities``; optional methods default to
``NotImplementedError`` so the dashboard can degrade gracefully for backends that
do not support a given dimension (e.g. drift/memory are ZizkaDB-only).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar, List, Optional, Set

from dbgpt.component import SystemApp
from dbgpt.observability.capability import Capability
from dbgpt.observability.models import (
    AgentStats,
    AgentSummary,
    CausalChain,
    DriftReport,
    EventHit,
    HealthRow,
    MemoryContext,
    Metric,
    MetricFilter,
    ModelUsageSummary,
    SessionDiff,
    SessionSummary,
    Timeseries,
    TimeWindow,
    TraceFilter,
    TraceSummary,
    TraceTree,
)


class ObservabilityProvider(ABC):
    """Abstract pluggable observability backend."""

    name: ClassVar[str] = "observability_provider"
    capabilities: ClassVar[Set[Capability]] = set()

    def __init__(self) -> None:
        self._system_app: Optional[SystemApp] = None

    def init_app(self, system_app: SystemApp) -> None:
        self._system_app = system_app

    def supports(self, capability: Capability) -> bool:
        return capability in self.capabilities

    # ---- fleet / agent dimension (required) ----
    @abstractmethod
    def list_agents(
        self, time_from: Optional[datetime] = None, time_to: Optional[datetime] = None
    ) -> List[AgentSummary]:
        """List agents with summary stats over the (optional) time window."""

    @abstractmethod
    def search_traces(self, filter: TraceFilter) -> List[TraceSummary]:
        """Search traces by filter, newest first."""

    @abstractmethod
    def get_trace(self, trace_id: str) -> Optional[TraceTree]:
        """Return the full span tree for a trace, or None if not found."""

    def agent_stats(self, agent_name: str) -> AgentStats:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement agent_stats"
        )

    def agent_health_matrix(
        self, time_from: Optional[datetime] = None, time_to: Optional[datetime] = None
    ) -> List[HealthRow]:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement agent_health_matrix"
        )

    # ---- metrics (Capability.METRICS) ----
    def model_usage(
        self, time_from: Optional[datetime] = None, time_to: Optional[datetime] = None
    ) -> List[ModelUsageSummary]:
        """Per-model token/call/latency aggregation (AntCC-style token panel)."""
        raise NotImplementedError(
            f"{type(self).__name__} does not implement model_usage"
        )

    def get_metrics(
        self,
        metric: Metric,
        window: TimeWindow,
        filter: Optional[MetricFilter] = None,
    ) -> Timeseries:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_metrics "
            f"(metric={metric.value})"
        )

    # ---- sessions (Capability.TRACES is enough for default) ----
    def list_sessions(
        self, agent_name: Optional[str] = None, limit: int = 50
    ) -> List[SessionSummary]:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement list_sessions"
        )

    def get_session_diff(self, session_id: str) -> SessionDiff:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_session_diff"
        )

    # ---- causal chain (Capability.CAUSAL_CHAIN) ----
    def get_causal_chain(self, span_id: str, depth: int = 10) -> CausalChain:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_causal_chain"
        )

    # ---- drift (Capability.DRIFT) ----
    def detect_drift(self, agent_name: str) -> DriftReport:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement detect_drift"
        )

    def drift_history(self, agent_name: str, days: int = 30) -> Timeseries:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement drift_history"
        )

    # ---- semantic search / memory (Capability.SEMANTIC_SEARCH / MEMORY) ----
    def semantic_search(
        self,
        query: str,
        agent_name: Optional[str] = None,
        limit: int = 10,
    ) -> List[EventHit]:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement semantic_search"
        )

    def get_memory_context(
        self, agent_name: str, task: str, max_tokens: int = 2000
    ) -> MemoryContext:
        raise NotImplementedError(
            f"{type(self).__name__} does not implement get_memory_context"
        )
