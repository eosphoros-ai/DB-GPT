"""Capability declaration for the observability read-side protocol.

Each ``ObservabilityProvider`` implementation declares which capabilities it
supports; the product UI degrades gracefully based on the declared set (e.g.
the ZizkaDB backend exposes drift/memory, the default SQLite backend does not).
"""

from enum import Enum


class Capability(str, Enum):
    """Capabilities an :class:`ObservabilityProvider` can expose."""

    TRACES = "traces"
    """Span tree for a single request/execution."""

    CAUSAL_CHAIN = "causal_chain"
    """Semantic causal chain (``why()``) — beyond raw parent_span_id linkage."""

    METRICS = "metrics"
    """Time-series aggregation: rate, p50/p95/p99 latency, token/cost rate."""

    DRIFT = "drift"
    """Behavioural drift detection across time windows."""

    SEMANTIC_SEARCH = "semantic_search"
    """Natural-language / embedding search over agent events."""

    MEMORY = "memory"
    """Agent memory retrieval / context injection (``context_for()``)."""
