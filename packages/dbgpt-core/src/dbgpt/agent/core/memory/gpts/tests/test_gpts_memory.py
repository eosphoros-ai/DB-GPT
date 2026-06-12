import asyncio
import json

from dbgpt.agent.core.action.base import ActionOutput
from dbgpt.agent.core.memory.gpts import (
    DefaultGptsMessageMemory,
    DefaultGptsPlansMemory,
    GptsMemory,
    GptsMessage,
)


def _message(
    *,
    rounds: int,
    content: str,
    action_report: str | None = None,
    is_success: bool = True,
) -> GptsMessage:
    return GptsMessage(
        conv_id="conv-1",
        sender="ReActToolMaster",
        receiver="ReActToolMaster",
        role="assistant",
        content=content,
        rounds=rounds,
        is_success=is_success,
        app_code="react_agent",
        app_name="ReAct",
        action_report=action_report,
    )


def test_get_agent_history_memory_recovers_action_reports_from_any_message():
    memory = GptsMemory(
        plans_memory=DefaultGptsPlansMemory(),
        message_memory=DefaultGptsMessageMemory(),
    )
    sql = "SELECT * FROM dim_line_station_rel WHERE line_code = '1'"
    action_output = ActionOutput(
        content="sql result",
        action="sql_query",
        action_input=json.dumps({"sql": sql}, ensure_ascii=False),
        memory_fragments={
            "memory": json.dumps(
                {
                    "question": "1路有那些站点",
                    "action": "sql_query",
                    "action_input": json.dumps({"sql": sql}, ensure_ascii=False),
                    "observation": "10 | 金宝商业广场",
                },
                ensure_ascii=False,
            ),
            "id": "fragment-1",
        },
    )

    memory.message_memory.append(
        _message(
            rounds=1,
            content="sql action",
            action_report=json.dumps(action_output.to_dict(), ensure_ascii=False),
        )
    )
    memory.message_memory.append(_message(rounds=2, content="display result"))

    recovered = asyncio.run(
        memory.get_agent_history_memory("conv-1", "ReActToolMaster")
    )

    assert len(recovered) == 1
    assert recovered[0].action == "sql_query"
    assert recovered[0].memory_fragments["id"] == "fragment-1"
