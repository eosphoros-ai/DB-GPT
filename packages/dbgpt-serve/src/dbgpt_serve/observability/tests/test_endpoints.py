"""HTTP smoke tests for the observability serve endpoints.

Builds a standalone FastAPI app, registers the observability :class:`Service`
component (which constructs the default provider against a temp SQLite store),
seeds one trace, then exercises the read endpoints via an in-process
:class:`AsyncClient`.
"""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from dbgpt.component import SystemApp
from dbgpt.observability.span_store import (
    ObservabilitySpanEntity,
    get_observability_store,
)
from dbgpt.util import AppConfig
from dbgpt.util.fastapi import create_app

from ..api.endpoints import init_endpoints, router
from ..config import ServeConfig

BASE = datetime(2026, 1, 1, 10, 0, 0)


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
                model_name="deepseek-chat",
                conversation_id="conv_0",
                start_time=BASE,
                end_time=BASE + timedelta(milliseconds=42),
                duration_ms=42,
                status="OK",
                total_tokens=7,
                cost=0.001,
                metadata_json="{}",
            )
        )
        session.commit()


@pytest_asyncio.fixture
async def client(tmp_path):
    sqlite_path = str(tmp_path / "obs.db")
    _seed(sqlite_path)
    app = create_app()
    system_app = SystemApp(app, AppConfig(configs={}))
    config = ServeConfig(sqlite_path=sqlite_path)
    init_endpoints(system_app, config)
    app.include_router(router, prefix="/api/v1/observability")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.mark.asyncio
async def test_capabilities(client: AsyncClient):
    resp = await client.get("/api/v1/observability/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"]
    caps = body["data"]
    assert "traces" in caps
    assert "metrics" in caps
    assert "drift" not in caps


@pytest.mark.asyncio
async def test_list_agents(client: AsyncClient):
    resp = await client.get("/api/v1/observability/agents")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["agent_name"] == "codeAuto"
    assert data[0]["event_count"] == 1


@pytest.mark.asyncio
async def test_search_traces(client: AsyncClient):
    resp = await client.get("/api/v1/observability/traces")
    assert resp.status_code == 200
    summaries = resp.json()["data"]
    assert len(summaries) == 1
    assert summaries[0]["trace_id"] == "t1"
    assert summaries[0]["span_count"] == 1


@pytest.mark.asyncio
async def test_get_trace(client: AsyncClient):
    resp = await client.get("/api/v1/observability/traces/t1")
    assert resp.status_code == 200
    tree = resp.json()["data"]
    assert tree["trace_id"] == "t1"
    assert tree["span_count"] == 1
    assert tree["root"]["span_id"] == "s1"


@pytest.mark.asyncio
async def test_get_metrics_event_volume(client: AsyncClient):
    start = (BASE - timedelta(hours=1)).isoformat()
    end = (BASE + timedelta(hours=2)).isoformat()
    resp = await client.get(
        "/api/v1/observability/metrics",
        params={
            "metric": "event_volume",
            "start": start,
            "end": end,
            "granularity": "hour",
        },
    )
    assert resp.status_code == 200
    ts = resp.json()["data"]
    assert ts["metric"] == "event_volume"
    assert ts["points"][0]["value"] == 1.0
