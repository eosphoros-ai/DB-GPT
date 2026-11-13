"""MCP tool results with isError=true must be recorded as failed actions."""

import json
from types import SimpleNamespace

import pytest

from dbgpt.agent.expand.actions.tool_action import (
    ToolCallSpec,
    run_tool,
    run_tools_batch,
)
from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack, mcp_tool_result_or_raise


class _McpResult:
    """Minimal stand-in for mcp.types.CallToolResult."""

    def __init__(self, text: str, is_error: bool):
        self.content = [SimpleNamespace(text=text)]
        self.isError = is_error

    def __str__(self) -> str:
        return f"content={self.content!r} structuredContent=None isError={self.isError}"


@tool(description="Refund an order.")
def create_refund(order_id: str, amount: float) -> _McpResult:
    return _McpResult(
        "Error executing tool create_refund: payment provider declined "
        "the refund: card expired",
        is_error=True,
    )


@tool(description="Return ok.")
def ping() -> _McpResult:
    return _McpResult("ok", is_error=False)


@tool(description="Refund an order (local tool).")
def local_refund(order_id: str, amount: float) -> str:
    raise RuntimeError("payment provider declined the refund: card expired")


def _pack(*tools):
    return ToolPack([fn._tool for fn in tools])


@pytest.mark.asyncio
async def test_mcp_iserror_result_is_a_failed_action():
    """A CallToolResult with isError=true used to be stored as success.

    Only transport exceptions and JSON bodies with success=false were treated
    as failures. str(CallToolResult) is a Python repr, not JSON, so a failed
    MCP call was recorded with is_exe_success=True. A local Python tool that
    raises the same error is already marked failed.
    """
    mcp_out = await run_tool(
        "create_refund",
        {"order_id": "B-2002", "amount": 1000},
        _pack(create_refund),
        need_vis_render=False,
    )
    local_out = await run_tool(
        "local_refund",
        {"order_id": "B-2002", "amount": 1000},
        _pack(local_refund),
        need_vis_render=False,
    )

    assert local_out.is_exe_success is False
    assert "card expired" in local_out.content
    assert mcp_out.is_exe_success is False
    assert "card expired" in (mcp_out.content or "") + (mcp_out.observations or "")


@pytest.mark.asyncio
async def test_mcp_success_result_still_succeeds():
    out = await run_tool("ping", {}, _pack(ping), need_vis_render=False)
    assert out.is_exe_success is True
    assert "ok" in (out.content or "")


@pytest.mark.asyncio
async def test_run_tools_batch_marks_a_failed_mcp_call():
    out = await run_tools_batch(
        [
            ToolCallSpec(name="ping", args={}),
            ToolCallSpec(
                name="create_refund", args={"order_id": "B-2002", "amount": 1000}
            ),
        ],
        _pack(ping, create_refund),
        need_vis_render=False,
    )
    assert out.is_exe_success is False
    results = json.loads(out.observations)
    by_name = {item["name"]: item for item in results}
    assert by_name["ping"]["success"] is True
    assert by_name["create_refund"]["success"] is False


def test_mcp_tool_result_or_raise_rejects_iserror():
    with pytest.raises(ValueError, match="card expired"):
        mcp_tool_result_or_raise(
            _McpResult(
                "payment provider declined the refund: card expired", is_error=True
            ),
            "create_refund",
        )


def test_mcp_tool_result_or_raise_returns_a_successful_result():
    result = _McpResult("ok", is_error=False)
    assert mcp_tool_result_or_raise(result, "ping") is result
