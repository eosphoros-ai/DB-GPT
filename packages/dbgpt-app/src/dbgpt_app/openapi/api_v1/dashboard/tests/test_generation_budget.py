import asyncio
import json
import threading

import pytest

from dbgpt.agent.expand.actions.tool_action import run_tool
from dbgpt_app.openapi.api_v1.dashboard.confirmation import (
    generation_failure,
    generation_start_event,
    run_bounded_generation,
)
from dbgpt_app.openapi.api_v1.dashboard.generation_budget import (
    DashboardGenerationTimeout,
    GenerationBudget,
    check_generation_deadline,
    generation_read,
    generation_timeout_seconds,
)

from . import test_confirmation_continuity
from .test_confirmation_continuity import planned, query
from .test_publication import _schema

environment = test_confirmation_continuity.environment


@pytest.mark.asyncio
async def test_late_publication_read_cannot_start_the_next_component(monkeypatch):
    from dbgpt_app.openapi.api_v1.dashboard.publication import (
        DashboardPublicationService,
    )

    service = DashboardPublicationService()
    release, finished = threading.Event(), threading.Event()
    calls = []

    def delayed(schema, widget, executor):
        calls.append(widget.id)
        release.wait(2)

    monkeypatch.setattr(service, "_materialize_widget", delayed)

    def materialize():
        try:
            service.validate_materialization(_schema(), None)
        finally:
            finished.set()

    async def work():
        return await generation_read(materialize)

    try:
        with pytest.raises(DashboardGenerationTimeout):
            await GenerationBudget(0.08).run(work)
        assert len(calls) == 1 and not finished.is_set()
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 1)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, 180),
        ("60", 60),
        ("300", 300),
        ("0", 180),
        ("600", 180),
        ("-1", 180),
        ("nan", 180),
        ("", 180),
    ],
)
def test_configuration_is_finite_and_bounded(monkeypatch, value, expected):
    monkeypatch.delenv("DBGPT_DASHBOARD_GENERATION_TIMEOUT_SECONDS", raising=False)
    if value is not None:
        monkeypatch.setenv("DBGPT_DASHBOARD_GENERATION_TIMEOUT_SECONDS", value)
    assert generation_timeout_seconds() == expected


@pytest.mark.asyncio
async def test_slow_model_is_cancelled_not_retried(environment):
    dashboard_id = await planned(environment)
    state, _ = environment[0](
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    budget = state["_dashboard_generation_budget"] = GenerationBudget(0.02)
    calls, stopped = [], asyncio.Event()

    async def model():
        calls.append("model")
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    assert generation_start_event(state)["limit_seconds"] == 0.02
    with pytest.raises(DashboardGenerationTimeout):
        await asyncio.wait_for(run_bounded_generation(state, model), timeout=1)
    assert stopped.is_set() and calls == ["model"]
    assert budget.stop_reason == "timeout"
    failure = generation_failure(state)
    assert failure["reason"] == "timeout"
    assert failure["stage_label"] == "模型生成 SQL"
    assert failure["validated_widget_ids"] == []
    assert failure["pending_widget_ids"] == [f"sales-{i}" for i in range(3)]
    assert "不会自动重试" in failure["retry_hint"]
    assert environment[1].rows[dashboard_id].current_revision == 1
    json.dumps(failure)  # No internal timers/coroutines leak into SSE/history.


@pytest.mark.asyncio
async def test_slow_query_keeps_truthful_progress_and_cannot_save_late(
    environment, monkeypatch
):
    dashboard_id = await planned(environment)
    state, pack = environment[0](
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    state["_dashboard_generation_budget"] = GenerationBudget(0.08)
    connector = environment[2]
    original = connector.query_ex
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    calls = []

    def delayed(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            entered.set()
            try:
                release.wait(2)
            finally:
                finished.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(connector, "query_ex", delayed)

    async def generate():
        return await run_tool(
            "create_dashboard_draft",
            {
                "widget_queries": {"widgets": [query(f"sales-{i}") for i in range(3)]},
            },
            pack,
        )

    try:
        with pytest.raises(DashboardGenerationTimeout):
            await asyncio.wait_for(run_bounded_generation(state, generate), timeout=1)
        assert entered.is_set() and not finished.is_set()
        failure = generation_failure(state)
        assert failure["stage_label"] == "组件 SQL 试运行"
        assert failure["validated_widget_ids"] == ["sales-0"]
        assert failure["pending_widget_ids"] == ["sales-1", "sales-2"]
        assert failure.get("saved_revision") is None
        assert len(calls) == 2
        assert environment[1].rows[dashboard_id].current_revision == 1
    finally:
        release.set()
        await asyncio.to_thread(finished.wait, 1)
    assert len(calls) == 2  # No third query or late mutation after the read returns.
    assert environment[1].rows[dashboard_id].current_revision == 1


@pytest.mark.asyncio
async def test_deadline_checked_at_atomic_save_boundary(environment, monkeypatch):
    dashboard_id = await planned(environment)
    state, pack = environment[0](
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    budget = state["_dashboard_generation_budget"] = GenerationBudget(10)
    # Simulate time expiring during the synchronous final schema validation.
    from dbgpt_app.openapi.api_v1.dashboard.service import DashboardService

    original = DashboardService.validate_schema

    def expire_at_validation(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        budget.started_at -= 20
        return result

    monkeypatch.setattr(DashboardService, "validate_schema", expire_at_validation)

    async def generate():
        return await run_tool(
            "create_dashboard_draft",
            {
                "widget_queries": {"widgets": [query(f"sales-{i}") for i in range(3)]},
            },
            pack,
        )

    # Tool wrappers may return an ActionOutput failure; the DAO must not write.
    await run_bounded_generation(state, generate)
    failure = generation_failure(state)
    assert failure["reason"] == "timeout"
    assert failure["stage_label"] == "保存看板草稿"
    assert failure["validated_widget_ids"] == [f"sales-{i}" for i in range(3)]
    assert environment[1].rows[dashboard_id].current_revision == 1


@pytest.mark.asyncio
async def test_saved_partial_revision_remains_distinct_from_trial_success(environment):
    dashboard_id = await planned(environment)
    state, pack = environment[0](
        f"[[confirm-dashboard:{dashboard_id}]] confirm revision 1"
    )
    broken = query("sales-2")
    broken["sql"] += " /* runtime_fail */"
    await run_tool(
        "create_dashboard_draft",
        {
            "widget_queries": {"widgets": [query("sales-0"), query("sales-1"), broken]},
        },
        pack,
    )
    failure = generation_failure(state)
    assert failure["saved_revision"] == 2
    assert failure["saved_widget_ids"] == ["sales-0", "sales-1"]
    assert failure["failed_widget_ids"] == ["sales-2"]
    assert failure["revision_prompt"] is None  # Don't reconfirm stale revision 1.


@pytest.mark.asyncio
async def test_disconnect_cancellation_remains_cancellation():
    budget = GenerationBudget(10)
    started = asyncio.Event()

    async def work():
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(budget.run(work))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert budget.stop_reason == "cancelled"
    with pytest.raises(DashboardGenerationTimeout):
        budget.check()
    check_generation_deadline()  # Context was reset; ordinary edits are unaffected.


@pytest.mark.asyncio
async def test_ordinary_chat_and_upstream_timeouts_are_not_generation_deadlines():
    async def work():
        return "ordinary chat or planning"

    assert await run_bounded_generation({}, work) == "ordinary chat or planning"
    budget = GenerationBudget(10)

    async def upstream_timeout():
        raise TimeoutError("upstream read timed out")

    with pytest.raises(TimeoutError, match="upstream read timed out"):
        await budget.run(upstream_timeout)
    assert budget.stop_reason is None
