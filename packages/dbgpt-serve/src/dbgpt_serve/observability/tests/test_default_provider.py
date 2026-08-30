"""Unit tests for :class:`DefaultObservabilityProvider` metrics + trace reads.

Builds a deterministic span sequence in a temp isolated SQLite store and asserts:
  * latency p50 / p95 / p99 (Python-side nearest-rank on per-bucket durations),
  * rate metrics (event_volume / token_rate / cost_rate / error_rate) via SQL
    bucketing,
  * trace search + trace-tree assembly (parent_span_id → children).

The store is keyed by absolute path, so a per-test ``tmp_path`` sqlite file
gives a fresh, isolated backend.
"""

from datetime import datetime, timedelta

import pytest

from dbgpt.observability.capability import Capability
from dbgpt.observability.default_provider import (
    DefaultObservabilityProvider,
    _percentile,
)
from dbgpt.observability.models import (
    Granularity,
    Metric,
    MetricFilter,
    TimeWindow,
    TraceFilter,
)
from dbgpt.observability.span_store import (
    ObservabilitySpanEntity,
    get_observability_store,
)

# Deterministic span set: 5 spans, one root (agent.run) and 4 children.
# Durations: [10, 20, 30, 40, 100] ms  -> p50=30, p95=100, p99=100.
# Tokens:    [10, 20, 30, 40, 100]     -> sum=200.
# One ERROR  (the 100ms one).
BASE = datetime(2026, 1, 1, 10, 0, 0)
SPANS = [
    # span_id, parent, op, agent, model, dur_ms, tokens, status, cost
    ("s1", None, "agent.run", "codeAuto", None, 10, 10, "OK", 0.0),
    ("s2", "s1", "llm.chat", "codeAuto", "deepseek-chat", 20, 20, "OK", 0.001),
    ("s3", "s1", "tool.search", "codeAuto", None, 30, 30, "OK", 0.0),
    ("s4", "s1", "llm.chat", "codeAuto", "deepseek-chat", 40, 40, "OK", 0.002),
    ("s5", "s1", "llm.chat", "codeAuto", "deepseek-chat", 100, 100, "ERROR", 0.01),
]


def _seed(sqlite_path: str) -> None:
    _, factory = get_observability_store(sqlite_path)
    with factory() as session:
        for i, (sid, parent, op, agent, model, dur, tokens, status, cost) in enumerate(
            SPANS
        ):
            start = BASE + timedelta(seconds=i)
            end = start + timedelta(milliseconds=dur)
            session.add(
                ObservabilitySpanEntity(
                    trace_id="t1",
                    span_id=sid,
                    parent_span_id=parent,
                    span_type="agent" if parent is None else "llm",
                    operation_name=op,
                    agent_name=agent,
                    model_name=model,
                    # Alternate conv_0 / conv_1 across the 5 spans.
                    conversation_id=f"conv_{i % 2}",
                    start_time=start,
                    end_time=end,
                    duration_ms=dur,
                    status=status,
                    total_tokens=tokens,
                    cost=cost,
                    metadata_json="{}",
                )
            )
        session.commit()


@pytest.fixture
def provider(tmp_path):
    sqlite_path = str(tmp_path / "obs.db")
    _seed(sqlite_path)
    return DefaultObservabilityProvider(sqlite_path=sqlite_path)


def _window() -> TimeWindow:
    return TimeWindow(
        start=BASE - timedelta(hours=1),
        end=BASE + timedelta(hours=2),
        granularity=Granularity.HOUR,
    )


# ---- percentile helper ----
def test_percentile_helper_known_values():
    assert _percentile([10, 20, 30, 40, 100], 50) == 30
    assert _percentile([10, 20, 30, 40, 100], 95) == 100
    assert _percentile([10, 20, 30, 40, 100], 99) == 100
    assert _percentile([], 50) == 0.0


# ---- capabilities ----
def test_capabilities_default_only(provider):
    assert Capability.TRACES in provider.capabilities
    assert Capability.METRICS in provider.capabilities
    assert Capability.DRIFT not in provider.capabilities


# ---- latency metrics ----
@pytest.mark.parametrize(
    "metric,expected",
    [
        (Metric.LATENCY_P50, 30.0),
        (Metric.LATENCY_P95, 100.0),
        (Metric.LATENCY_P99, 100.0),
    ],
)
def test_latency_percentiles(provider, metric, expected):
    ts = provider.get_metrics(metric, _window())
    assert ts.metric == metric
    assert len(ts.points) == 1, "all spans fall in one hour bucket"
    assert ts.points[0].value == pytest.approx(expected)
    assert ts.points[0].timestamp == datetime(2026, 1, 1, 10, 0)


# ---- rate metrics ----
def test_event_volume(provider):
    ts = provider.get_metrics(Metric.EVENT_VOLUME, _window())
    assert ts.points[0].value == 5.0


def test_token_rate(provider):
    ts = provider.get_metrics(Metric.TOKEN_RATE, _window())
    assert ts.points[0].value == 200.0


def test_cost_rate(provider):
    ts = provider.get_metrics(Metric.COST_RATE, _window())
    # 0.0 + 0.001 + 0.0 + 0.002 + 0.01
    assert ts.points[0].value == pytest.approx(0.013)


def test_error_rate(provider):
    ts = provider.get_metrics(Metric.ERROR_RATE, _window())
    assert ts.points[0].value == pytest.approx(0.2)


# ---- metric filter model_name ----
def test_metric_filter_model_name(provider):
    flt = MetricFilter(model_name="deepseek-chat")
    # Only the 3 llm.chat spans (s2, s4, s5) -> tokens 20+40+100 = 160, events 3.
    vol = provider.get_metrics(Metric.EVENT_VOLUME, _window(), flt)
    tok = provider.get_metrics(Metric.TOKEN_RATE, _window(), flt)
    assert vol.points[0].value == 3.0
    assert tok.points[0].value == 160.0


# ---- trace search ----
def test_search_traces_returns_summary(provider):
    summaries = provider.search_traces(TraceFilter(limit=10))
    assert len(summaries) == 1
    s = summaries[0]
    assert s.trace_id == "t1"
    assert s.span_count == 5
    assert s.root_operation_name == "agent.run"
    # ERROR span present -> status ERROR
    assert s.status == "ERROR"


def test_search_traces_filter_by_agent(provider):
    summaries = provider.search_traces(TraceFilter(agent_name="nonexistent"))
    assert summaries == []


# ---- trace tree ----
def test_get_trace_assembles_tree(provider):
    tree = provider.get_trace("t1")
    assert tree is not None
    assert tree.trace_id == "t1"
    assert tree.span_count == 5
    assert tree.status == "ERROR"
    assert tree.root.span_id == "s1"
    assert tree.root.parent_span_id is None
    assert len(tree.root.children) == 4


def test_get_trace_missing(provider):
    assert provider.get_trace("does-not-exist") is None


# ---- list agents ----
def test_list_agents(provider):
    agents = provider.list_agents()
    assert len(agents) == 1
    assert agents[0].agent_name == "codeAuto"
    assert agents[0].event_count == 5
