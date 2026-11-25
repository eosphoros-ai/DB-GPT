import asyncio

import pytest

from dbgpt.util.retry import async_retry


@pytest.mark.asyncio
async def test_async_retry_propagates_excluded_exception_without_retrying():
    failure = RuntimeError("original failure")
    calls = 0

    @async_retry(retries=3, catch_exceptions=(ValueError,))
    async def fail_with_runtime_error():
        nonlocal calls
        calls += 1
        raise failure

    with pytest.raises(RuntimeError) as exc_info:
        await fail_with_runtime_error()

    assert exc_info.value is failure
    assert calls == 1


@pytest.mark.asyncio
async def test_async_retry_propagates_cancellation_by_default():
    calls = 0

    @async_retry(retries=3)
    async def cancel():
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError("cancel operation")

    with pytest.raises(asyncio.CancelledError):
        await cancel()

    assert calls == 1


@pytest.mark.asyncio
async def test_async_retry_can_explicitly_catch_cancellation():
    calls = 0

    @async_retry(retries=2, catch_exceptions=(BaseException,))
    async def cancel_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise asyncio.CancelledError("retry cancellation")
        return "completed"

    assert await cancel_once() == "completed"
    assert calls == 2


@pytest.mark.asyncio
async def test_async_retry_retries_caught_exception_until_success():
    calls = 0

    @async_retry(retries=3, catch_exceptions=(ValueError,))
    async def fail_twice():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("temporary failure")
        return "completed"

    assert await fail_twice() == "completed"
    assert calls == 3


@pytest.mark.asyncio
async def test_async_retry_raises_last_caught_exception_after_exhaustion():
    calls = 0
    failures = [ValueError("first failure"), ValueError("last failure")]

    @async_retry(retries=2, catch_exceptions=(ValueError,))
    async def always_fail():
        nonlocal calls
        failure = failures[calls]
        calls += 1
        raise failure

    with pytest.raises(ValueError) as exc_info:
        await always_fail()

    assert exc_info.value is failures[-1]
    assert calls == 2


@pytest.mark.asyncio
async def test_async_retry_returns_first_success_in_parallel_result_order():
    calls = 0

    @async_retry(retries=2, parallel_executions=3)
    async def sometimes_fail():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("retryable failure")
        return f"success {calls}"

    assert await sometimes_fail() == "success 2"
    assert calls == 3


@pytest.mark.asyncio
async def test_async_retry_propagates_excluded_exception_before_later_success():
    calls = 0
    failure = RuntimeError("excluded failure")

    @async_retry(retries=2, parallel_executions=2, catch_exceptions=(ValueError,))
    async def fail_then_succeed():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise failure
        return "success"

    with pytest.raises(RuntimeError) as exc_info:
        await fail_then_succeed()

    assert exc_info.value is failure
    assert calls == 2


@pytest.mark.asyncio
async def test_async_retry_returns_earlier_success_before_later_excluded_exception():
    calls = 0
    failure = RuntimeError("later excluded failure")

    @async_retry(retries=2, parallel_executions=2, catch_exceptions=(ValueError,))
    async def succeed_then_fail():
        nonlocal calls
        calls += 1
        if calls == 1:
            return "success"
        raise failure

    assert await succeed_then_fail() == "success"
    assert calls == 2
