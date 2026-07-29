"""Tests for bounded sub-agent history snapshots."""

import json
from unittest.mock import patch

from dbgpt_app.openapi.api_v1.subagent import history as history_module
from dbgpt_app.openapi.api_v1.subagent.history import (
    MAX_SUBAGENT_HISTORY_BYTES,
    build_subagent_history_snapshot,
    fail_running_subagent_history,
    update_subagent_history,
)


def _stored_subagent_increment(snapshot):
    base_payload = json.dumps({"_base": None}, ensure_ascii=False)
    snapshot_payload = json.dumps(
        {"_base": None, "sub_agents": snapshot},
        ensure_ascii=False,
    )
    base_record = json.dumps({"content": base_payload}, ensure_ascii=False)
    snapshot_record = json.dumps({"content": snapshot_payload}, ensure_ascii=False)
    return len(snapshot_record.encode("utf-8")) - len(base_record.encode("utf-8"))


def test_subagent_history_restores_structured_execution_state():
    """Keep the fields required by the history execution-detail UI."""
    state = {}
    update_subagent_history(
        state,
        {
            "type": "agent.start",
            "agent_id": "sub_d1_0",
            "agent_name": "Country distribution",
            "goal": "Analyze users by country",
            "lane": 0,
            "batch_id": 1,
        },
    )
    update_subagent_history(
        state,
        {
            "type": "agent.step",
            "agent_id": "sub_d1_0",
            "batch_id": 1,
            "action": "sql_query",
            "intention": "Count users by country",
            "sql": "SELECT country, COUNT(*) FROM users GROUP BY country",
            "chunks": [
                {
                    "output_type": "markdown",
                    "content": "| country | count |\n| --- | --- |\n| USA | 5 |",
                }
            ],
        },
    )
    update_subagent_history(
        state,
        {
            "type": "agent.done",
            "agent_id": "sub_d1_0",
            "batch_id": 1,
            "status": "done",
            "result": "USA has 5 users.",
            "elapsed_ms": 1200,
        },
    )
    update_subagent_history(
        state,
        {
            "type": "subagent.artifacts",
            "items": [
                {
                    "type": "image",
                    "url": "/images/country.png",
                    "agent_id": "sub_d1_0",
                    "agent_name": "Country distribution",
                }
            ],
        },
    )

    snapshot = build_subagent_history_snapshot(state)

    assert snapshot == [
        {
            "agent_id": "sub_d1_0",
            "name": "Country distribution",
            "goal": "Analyze users by country",
            "status": "done",
            "lane": 0,
            "batch_id": 1,
            "artifact_count": 1,
            "artifacts": [
                {
                    "type": "image",
                    "url": "/images/country.png",
                }
            ],
            "result": "USA has 5 users.",
            "elapsed_ms": 1200,
            "steps": [
                {
                    "action": "sql_query",
                    "intention": "Count users by country",
                    "sql": ("SELECT country, COUNT(*) FROM users GROUP BY country"),
                    "chunks": [
                        {
                            "output_type": "markdown",
                            "content": (
                                "| country | count |\n| --- | --- |\n| USA | 5 |"
                            ),
                        }
                    ],
                }
            ],
        }
    ]


def test_subagent_history_snapshot_is_bounded():
    """Keep history safely below the payload budget under large HTML output."""
    state = {}
    for agent_index in range(3):
        agent_id = f"sub_d1_{agent_index}"
        update_subagent_history(
            state,
            {
                "type": "agent.start",
                "agent_id": agent_id,
                "agent_name": f"Agent {agent_index}",
                "goal": "Generate reports " * 500,
                "lane": agent_index,
                "batch_id": 1,
            },
        )
        for step_index in range(15):
            update_subagent_history(
                state,
                {
                    "type": "agent.step",
                    "agent_id": agent_id,
                    "batch_id": 1,
                    "action": "html_interpreter",
                    "intention": f"Generate report {step_index} " * 200,
                    "sql": "SELECT '数据' AS value " * 1_000,
                    "chunks": [
                        {
                            "output_type": "html",
                            "content": "<html>" + ("x" * 200_000) + "</html>",
                        },
                        {
                            "output_type": "markdown",
                            "content": "结果" * 2_000,
                        },
                    ],
                },
            )

    snapshot = build_subagent_history_snapshot(state)
    stored_size = _stored_subagent_increment(snapshot)

    assert stored_size <= MAX_SUBAGENT_HISTORY_BYTES
    assert len(snapshot) == 3
    assert all(agent["steps"] for agent in snapshot)
    assert all(
        chunk.get("output_type") != "html"
        for agent in snapshot
        for step in agent["steps"]
        for chunk in step.get("chunks", [])
    )


def test_subagent_history_keeps_small_html_atomic():
    """Retain a complete report and its title when it fits the budget."""
    state = {}
    html = "<html><body><h1>Report</h1></body></html>"
    update_subagent_history(
        state,
        {
            "type": "agent.step",
            "agent_id": "sub_d1_0",
            "action": "html_interpreter",
            "chunks": [
                {
                    "output_type": "html",
                    "content": html,
                    "title": "Country report",
                }
            ],
        },
    )

    snapshot = build_subagent_history_snapshot(state)

    assert snapshot[0]["steps"][0]["chunks"] == [
        {
            "output_type": "html",
            "content": html,
            "title": "Country report",
        }
    ]


def test_subagent_history_finalizes_running_agents_on_error():
    """Historical conversations must not reopen with a permanent spinner."""
    state = {}
    update_subagent_history(
        state,
        {
            "type": "agent.start",
            "agent_id": "sub_d1_0",
            "agent_name": "Interrupted task",
        },
    )

    fail_running_subagent_history(state)

    assert state["sub_d1_0"]["status"] == "failed"
    assert "interrupted" in state["sub_d1_0"]["result"].lower()


def test_subagent_history_compaction_uses_bounded_serialization_passes():
    """Avoid serializing the full snapshot once per chunk or removed step."""
    state = {}
    for agent_index in range(30):
        agent_id = f"sub_d1_{agent_index}"
        update_subagent_history(
            state,
            {
                "type": "agent.start",
                "agent_id": agent_id,
                "agent_name": f"Agent {agent_index}",
                "goal": "目标" * 2_000,
                "lane": agent_index,
                "batch_id": 1,
            },
        )
        for step_index in range(15):
            update_subagent_history(
                state,
                {
                    "type": "agent.step",
                    "agent_id": agent_id,
                    "action": "sql_query",
                    "intention": "意图" * 500,
                    "sql": "SELECT '数据' " * 1_000,
                    "chunks": [
                        {
                            "output_type": "markdown",
                            "content": "结果" * 1_000,
                        }
                    ],
                },
            )

    max_bytes = 64 * 1024
    with patch.object(
        history_module,
        "_snapshot_size",
        wraps=history_module._snapshot_size,
    ) as measure:
        snapshot = build_subagent_history_snapshot(state, max_bytes=max_bytes)

    assert measure.call_count <= 16
    assert _stored_subagent_increment(snapshot) <= max_bytes
