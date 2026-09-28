"""Wiring tests: _post_sql_query must refuse to execute non-read-only SQL.

The LLM/agent response content arrives over HTTP (in AGENT mode from a
fully attacker-controlled URL), so before it reaches
``BenchmarkDataManager.query`` → ``session.execute(text(sql))`` it must
pass the read-only guard. Rejected statements must surface as the same
errorMsg flow as any other query failure — never as an executed query.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import dbgpt_serve.evaluate.service.benchmark.user_input_execute_service as uies

from ..service.benchmark.models import FileParseTypeEnum


@pytest.fixture
def service():
    return uies.UserInputExecuteService(
        compare_service=Mock(), file_type=FileParseTypeEnum.GITHUB
    )


def _input():
    return SimpleNamespace(
        serial_no=1,
        question="q",
        analysis_model_id="m1",
        llm_code="gpt-test",
        knowledge=None,
        prompt=None,
    )


def _response(content: str):
    return SimpleNamespace(content=content, cot_tokens=0)


async def _run(service, content, monkeypatch):
    manager = Mock()
    manager.query = AsyncMock(return_value=[])
    monkeypatch.setattr(uies, "get_benchmark_manager", lambda: manager)
    config = SimpleNamespace(execute_llm_result=True)
    answer = await service._post_sql_query(_input(), config, _response(content))
    return answer, manager


@pytest.mark.asyncio
async def test_read_only_sql_is_forwarded_to_the_manager(service, monkeypatch):
    answer, manager = await _run(service, "SELECT 1 AS one", monkeypatch)

    manager.query.assert_awaited_once()
    assert answer.errorMsg is None
    assert answer.llmOutput


@pytest.mark.asyncio
async def test_write_statement_is_never_executed(service, monkeypatch):
    answer, manager = await _run(
        service, "ATTACH DATABASE '/tmp/evil.db' AS evil", monkeypatch
    )

    manager.query.assert_not_awaited()
    assert answer.errorMsg is not None


@pytest.mark.asyncio
async def test_stacked_statement_is_never_executed(service, monkeypatch):
    answer, manager = await _run(service, "SELECT 1; DROP TABLE secrets", monkeypatch)

    manager.query.assert_not_awaited()
    assert answer.errorMsg is not None


@pytest.mark.asyncio
async def test_with_prefixed_dml_is_never_executed(service, monkeypatch):
    # SQLite allows WITH-prefixed DML (e.g. "WITH cte AS (...) INSERT");
    # the guard must reject it end-to-end, not just at keyword level
    answer, manager = await _run(
        service,
        "WITH cte AS (SELECT 1) INSERT INTO secrets VALUES ('PWNED')",
        monkeypatch,
    )

    manager.query.assert_not_awaited()
    assert answer.errorMsg is not None
