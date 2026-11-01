"""Published report IDs must identify committed runs, including under contention."""

import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event, Lock, get_ident
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import event

from dbgpt.core.interface.report_capture import (
    ArtifactCaptureContext,
    InMemoryArtifactSink,
    capture_python_execution,
)
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_app.openapi.api_v1 import agentic_data_api as api
from dbgpt_app.openapi.api_v1.react_final import AgentFinalAnswer
from dbgpt_serve.report.api import endpoints
from dbgpt_serve.report.config import ServeConfig
from dbgpt_serve.report.models import models
from dbgpt_serve.report.models.dao import ReportDao
from dbgpt_serve.report.serve import ReportServe
from dbgpt_serve.report.service import ReportService


@pytest.fixture
def persistence(tmp_path, monkeypatch):
    from dbgpt.configs import model_config

    monkeypatch.setattr(model_config, "PILOT_PATH", str(tmp_path))
    path = tmp_path / "reports.db"
    manager = DatabaseManager()
    manager.init_db(
        "sqlite:///" + path.as_posix(),
        engine_args={"connect_args": {"check_same_thread": False, "timeout": 10}},
    )
    tables = [
        models.ReportEntity.__table__,
        models.ReportRunEntity.__table__,
        models.ReportArtifactEntity.__table__,
        models.ReportArtifactDependencyEntity.__table__,
        models.ReportEvidenceEntity.__table__,
    ]
    models.ReportEntity.metadata.create_all(manager.engine, tables=tables)
    service = ReportService(ReportDao(manager))
    monkeypatch.setattr(
        ReportServe,
        "get_current_serve",
        classmethod(lambda cls, *args: SimpleNamespace(service=service)),
    )
    executor = ThreadPoolExecutor(max_workers=2)
    monkeypatch.setattr(api, "_REPORT_PERSIST_EXECUTOR", executor)
    monkeypatch.setattr(api, "_REPORT_PERSIST_SLOTS", BoundedSemaphore(2))
    monkeypatch.setattr(api, "_REPORT_PERSIST_TASKS", set())
    endpoints.init_endpoints(MagicMock(), service, ServeConfig())
    app = FastAPI()
    app.include_router(endpoints.router, prefix="/api/v1/reports")
    yield SimpleNamespace(
        path=path, service=service, app=app, executor=executor, manager=manager
    )
    executor.shutdown(wait=True)
    endpoints._reset_endpoints()
    manager.engine.dispose()


def turn(index, content="Analysis complete."):
    conv_id = f"publication-{index}"
    sink = InMemoryArtifactSink(
        ArtifactCaptureContext(conv_uid=conv_id, run_id=f"capture-{index}")
    )
    capture_python_execution(
        code="REPORT_RESULT = {'value': 42}",
        duration_ms=1,
        status="succeeded",
        exit_code=0,
        stdout="42",
        stderr="",
        result_inline={"value": 42},
        artifact_sink=sink,
    )
    return dict(
        dialogue=SimpleNamespace(user_name="alice"),
        conv_id=conv_id,
        user_input="Create report",
        final_answer=AgentFinalAnswer(content),
        artifact_sink=sink,
        react_state={
            "_report_presentation": {"format": "html", "content": "<h1>Report</h1>"}
        },
    )


def published(answer):
    history = api._build_react_history_payload(
        final_content=answer.content,
        steps=[],
        task_plan=[],
        generated_images=[],
        sub_agents=[],
        input_files=[],
        report_id=answer.report_id,
        report_run_id=answer.report_run_id,
        report_status=answer.report_status,
    )
    storage = MagicMock()
    final, done = api._react_terminal_events(storage, history, answer)
    storage.add_view_message.assert_called_once_with(history)
    assert json.loads(done.removeprefix("data: "))["type"] == "done"
    return json.loads(history), json.loads(final.removeprefix("data: "))


async def get_run(app, answer):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        return await client.get(
            f"/api/v1/reports/{answer.report_id}/runs/{answer.report_run_id}",
            headers={"user-id": "alice"},
        )


def lock_database(persistence):
    lock = sqlite3.connect(persistence.path)
    lock.execute("BEGIN EXCLUSIVE")
    entered = set()
    guard = Lock()
    blocked = Event()

    def before_query(conn, cursor, statement, parameters, context, executemany):
        if (
            statement.lstrip().upper().startswith("SELECT")
            and "dbgpt_report" in statement
        ):
            with guard:
                entered.add(get_ident())
                if len(entered) == 2:
                    blocked.set()

    event.listen(persistence.manager.engine, "before_cursor_execute", before_query)
    return lock, blocked


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content", ["Analysis complete.", "Main workflow failed; rendered report retained."]
)
async def test_commit_precedes_history_and_final_publication(persistence, content):
    answer = await api._finalize_turn_report_persistence(**turn("ready", content))
    assert answer.report_status == "ready"
    for payload in published(answer):
        assert payload["report_status"] == "ready"
        assert payload["report_id"] == answer.report_id
        assert payload["report_run_id"] == answer.report_run_id
    response = await get_run(persistence.app, answer)
    assert response.status_code == 200, response.text
    assert not api._REPORT_PERSIST_TASKS


@pytest.mark.asyncio
async def test_saturated_workers_wait_and_all_published_runs_are_readable(
    persistence,
):
    lock, blocked = lock_database(persistence)
    tasks = [
        asyncio.create_task(api._finalize_turn_report_persistence(**turn(i)))
        for i in range(2)
    ]
    try:
        assert await asyncio.to_thread(blocked.wait, 2), (
            "Both real SQLite workers must block"
        )
        tasks.append(
            asyncio.create_task(api._finalize_turn_report_persistence(**turn(2)))
        )
        await asyncio.sleep(0.1)
        assert all(not task.done() for task in tasks)
    finally:
        lock.rollback()
        lock.close()
    answers = await asyncio.gather(*tasks)
    assert len(answers) == 3
    for answer in answers:
        assert answer.report_status == "ready"
        assert (await get_run(persistence.app, answer)).status_code == 200
        assert all(payload["report_status"] == "ready" for payload in published(answer))
    assert not api._REPORT_PERSIST_TASKS


@pytest.mark.asyncio
async def test_timeout_never_publishes_unconfirmed_ids_or_late_commits(
    persistence, monkeypatch
):
    monkeypatch.setattr(api, "_REPORT_PERSIST_TIMEOUT_SECONDS", 0.4)
    lock, blocked = lock_database(persistence)
    turns = [turn(i) for i in range(3)]
    tasks = [
        asyncio.create_task(api._finalize_turn_report_persistence(**t))
        for t in turns[:2]
    ]
    try:
        assert await asyncio.to_thread(blocked.wait, 2)
        tasks.append(
            asyncio.create_task(api._finalize_turn_report_persistence(**turns[2]))
        )
        answers = await asyncio.gather(*tasks)
        for answer in answers:
            for payload in published(answer):
                assert payload["report_status"] == "unconfirmed"
                assert "report_id" not in payload
                assert "report_run_id" not in payload
                assert (
                    payload.get("content", payload.get("final_content"))
                    == "Analysis complete."
                )
        assert not api._REPORT_PERSIST_TASKS
    finally:
        lock.rollback()
        lock.close()
        await asyncio.to_thread(persistence.executor.shutdown, wait=True)
    # Late completion of worker threads must not mutate the already-published
    # answers or reuse a stale run as a successful result for any turn.
    assert all(answer.report_status == "unconfirmed" for answer in answers)
    assert all("_report_run" not in t["react_state"] for t in turns)
    report_id, run_id = api._turn_report_coordinates(
        turns[2]["dialogue"],
        turns[2]["conv_id"],
        turns[2]["final_answer"],
        turns[2]["artifact_sink"],
        turns[2]["react_state"]["_report_presentation"],
    )
    candidate = AgentFinalAnswer("", report_id=report_id, report_run_id=run_id)
    assert (await get_run(persistence.app, candidate)).status_code == 404


@pytest.mark.asyncio
async def test_cancelled_waiters_do_not_leak_persistence_slots(persistence):
    lock, blocked = lock_database(persistence)
    tasks = [
        asyncio.create_task(api._finalize_turn_report_persistence(**turn(i)))
        for i in range(2)
    ]
    try:
        assert await asyncio.to_thread(blocked.wait, 2)
        tasks.append(
            asyncio.create_task(api._finalize_turn_report_persistence(**turn(2)))
        )
        await asyncio.sleep(0.05)
        for task in tasks:
            task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert all(isinstance(result, asyncio.CancelledError) for result in results)
    finally:
        lock.rollback()
        lock.close()
        await asyncio.to_thread(persistence.executor.shutdown, wait=True)
    assert not api._REPORT_PERSIST_TASKS
    assert api._REPORT_PERSIST_SLOTS.acquire(blocking=False)
    assert api._REPORT_PERSIST_SLOTS.acquire(blocking=False)
    assert not api._REPORT_PERSIST_SLOTS.acquire(blocking=False)
    api._REPORT_PERSIST_SLOTS.release()
    api._REPORT_PERSIST_SLOTS.release()


@pytest.mark.asyncio
async def test_failed_save_cannot_publish_stale_run(persistence, monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("Simulated storage failure")

    monkeypatch.setattr(persistence.service, "assemble_and_save", fail)
    params = turn("failed")
    params["react_state"]["_report_run"] = SimpleNamespace(
        report_id="old", run_id="old"
    )
    answer = await api._finalize_turn_report_persistence(**params)
    for payload in published(answer):
        assert payload["report_status"] == "unconfirmed"
        assert "report_id" not in payload
        assert "report_run_id" not in payload


@pytest.mark.asyncio
async def test_without_rendered_report_does_not_publish_coordinates(persistence):
    params = turn("no-html")
    params["react_state"].clear()
    answer = await api._finalize_turn_report_persistence(**params)
    assert answer.report_status is None
    assert answer.report_id is None
    assert answer.report_run_id is None
    assert not api._REPORT_PERSIST_TASKS
