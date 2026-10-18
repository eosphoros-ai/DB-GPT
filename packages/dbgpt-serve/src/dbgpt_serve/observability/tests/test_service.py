"""Tests for the observability service layer.

Verifies the service loads the default provider from ``ServeConfig.provider_cls``
and proxies capability/trace reads through to it.
"""

from datetime import datetime

import pytest

from dbgpt.component import SystemApp
from dbgpt.observability.base import ObservabilityProvider
from dbgpt.observability.default_provider import DefaultObservabilityProvider
from dbgpt.observability.span_store import (
    ObservabilitySpanEntity,
    get_observability_store,
)
from dbgpt_serve.core.tests.conftest import system_app  # noqa: F401

from ..api.endpoints import _dump
from ..config import ServeConfig
from ..service.service import Service


def _seed(sqlite_path: str) -> None:
    _, factory = get_observability_store(sqlite_path)
    with factory() as session:
        session.add(
            ObservabilitySpanEntity(
                trace_id="t1",
                span_id="s1",
                parent_span_id=None,
                span_type="agent",
                operation_name="agent.run",
                agent_name="codeAuto",
                start_time=datetime(2026, 1, 1, 10, 0, 0),
                end_time=datetime(2026, 1, 1, 10, 0, 0, 50000),
                duration_ms=50,
                status="OK",
                metadata_json="{}",
            )
        )
        session.commit()


@pytest.fixture
def service(system_app: SystemApp, tmp_path):
    sqlite_path = str(tmp_path / "obs.db")
    _seed(sqlite_path)
    cfg = ServeConfig(sqlite_path=sqlite_path)
    instance = Service(system_app, cfg)
    instance.init_app(system_app)
    return instance


def test_provider_is_default(service):
    assert isinstance(service.provider, DefaultObservabilityProvider)
    assert isinstance(service.provider, ObservabilityProvider)


def test_provider_capabilities(service):
    caps = service.provider.capabilities
    assert "traces" in {c.value for c in caps}
    assert "metrics" in {c.value for c in caps}


def test_provider_search_traces_seeded_data(service):
    from dbgpt.observability.models import TraceFilter

    summaries = service.provider.search_traces(TraceFilter(limit=10))
    assert len(summaries) == 1
    assert summaries[0].trace_id == "t1"
    # The endpoint serializer should handle the returned DTOs without error.
    assert _dump(summaries)[0]["trace_id"] == "t1"


def test_config_defaults():
    """The out-of-box default provider_cls points at the default SQLite backend."""
    cfg = ServeConfig()
    assert (
        cfg.provider_cls
        == "dbgpt.observability.default_provider.DefaultObservabilityProvider"
    )
    assert cfg.sqlite_path is None  # -> falls back to logs/observability.db


def test_default_provider_loads_without_seed_data(system_app, tmp_path):
    # A freshly-constructed service must build the provider against an empty
    # store and expose empty (not erroring) reads.
    cfg = ServeConfig(sqlite_path=str(tmp_path / "empty.db"))
    svc = Service(system_app, cfg)
    assert svc.provider is not None
    assert svc.provider.list_agents() == []
