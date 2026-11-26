"""Current analysis templates compile and execute independent Agent branches."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from dbgpt.core.awel.flow.flow_factory import FlowFactory, FlowPanel
from dbgpt_app.operators.agent_runner import SELECTABLE_TOOLS
from dbgpt_app.operators.taskflow import register_step_events, unregister_step_events
from dbgpt_app.operators.taskflow_agent import TFAgentOperator

from ..taskflow import TaskFlowDSLError, compile_taskflow

TEMPLATES = Path(__file__).parents[1] / "templates"


def load(language="zh"):
    return json.loads(
        (TEMPLATES / language / "taskflow-db-analysis-template.json").read_text()
    )["flow"]


@pytest.mark.parametrize("language", ["zh", "en"])
def test_current_template_dependencies_and_resources(language):
    flow = load(language)
    source = flow["taskflow_source"]
    compiled = compile_taskflow(source)
    agents = [node for node in compiled.nodes if "taskflow_agent_operator" in node.id]
    ids = {}
    for node in agents:
        parameters = {p.name: p.value for p in node.data.parameters}
        ids[parameters["step_id"]] = node.id
    edges = {(edge.source, edge.target) for edge in compiled.edges}
    assert (ids["n4"], ids["n8"]) not in edges
    assert (ids["n8"], ids["n4"]) not in edges
    for branch in ("n4", "n8"):
        assert (ids["n3"], ids[branch]) in edges
        assert (ids[branch], ids["n5"]) in edges
    for node in source["nodes"]:
        if node["kind"] == "agent":
            assert set(node["config"].get("tools", [])) <= set(SELECTABLE_TOOLS)
            assert not node["config"].get("skills")
    dag = FlowFactory().build(
        FlowPanel(
            name=flow["name"],
            label=flow["label"],
            flow_data=compiled,
        )
    )
    assert len(dag.trigger_nodes) == len(dag.leaf_nodes) == 1


@pytest.mark.asyncio
async def test_real_compiled_agents_overlap_and_review_waits(monkeypatch):
    """Model responses are controlled; compiler, runner and Agent events are real."""
    flow = load()
    source = flow["taskflow_source"]
    nodes = {node["id"]: node for node in source["nodes"]}
    goals = {
        node["config"]["goal"]: node_id
        for node_id, node in nodes.items()
        if node["kind"] == "agent"
    }
    started = set()
    finished = set()
    calls = []
    both_started = asyncio.Event()
    evidence = "semantic::fixture/metric/17@v1"

    async def agent(**kwargs):
        node_id = goals[kwargs["goal"]]
        assert kwargs["model"] == "test"
        calls.append(node_id)
        sections = "\n".join(section[2] for section in kwargs["upstream_sections"])
        if node_id in ("n4", "n8"):
            assert evidence in sections
            # Neither independent branch can see its sibling's answer.
            assert "branch-answer:" not in sections
            started.add(node_id)
            if len(started) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 1)
            await asyncio.sleep(0.02)
            finished.add(node_id)
            return f"branch-answer:{node_id} {evidence}"
        if node_id == "n5":
            assert finished == {"n4", "n8"}
            assert "branch-answer:n4" in sections and "branch-answer:n8" in sections
        return f"{node_id} {evidence}"

    monkeypatch.setattr("dbgpt_app.operators.taskflow_agent.run_react_agent", agent)
    compiled = compile_taskflow(source)
    dag = FlowFactory().build(
        FlowPanel(
            name=flow["name"],
            label=flow["label"],
            flow_data=compiled,
        )
    )
    queue = register_step_events("parallel-template-test")
    try:
        with patch.object(TFAgentOperator, "llm_client", new_callable=PropertyMock):
            result = await asyncio.wait_for(
                dag.leaf_nodes[0].call(
                    call_data={
                        "model": "test",
                        "messages": "分析净实收",
                        "stream": False,
                        "conv_uid": "parallel-template-test",
                    }
                ),
                5,
            )
        assert evidence in result
        assert len(calls) == len(set(calls)) == 6
        events = []
        while not queue.empty():
            text = queue.get_nowait()
            if "vis-flow-step" in text:
                events.append(
                    json.loads(text.split("```")[1].replace("vis-flow-step", ""))
                )
        branch_events = [e for e in events if e["step_id"] in ("n4", "n8")]
        first_success = next(
            i for i, e in enumerate(branch_events) if e["status"] == "success"
        )
        assert {e["step_id"] for e in branch_events[:first_success]} == {"n4", "n8"}
        assert {e["step_id"] for e in branch_events if e["status"] == "success"} == {
            "n4",
            "n8",
        }
        assert all(
            e["duration_ms"] >= 20 for e in branch_events if e["status"] == "success"
        )
    finally:
        unregister_step_events("parallel-template-test")


@pytest.mark.asyncio
async def test_connection_error_cannot_be_a_successful_agent_answer():
    operator = TFAgentOperator(goal="test")
    with (
        patch.object(TFAgentOperator, "llm_client", new_callable=PropertyMock),
        patch(
            "dbgpt_app.operators.taskflow_agent.run_react_agent",
            new=AsyncMock(
                return_value="LLM_PROVIDER_ERROR: [Errno 61] Connection refused"
            ),
        ),
    ):
        with pytest.raises(Exception, match="model provider error"):
            await operator._join_func("test")


def test_parallel_group_rejects_dependent_agents():
    source = load()["taskflow_source"]
    source["edges"].append(["n4", "n8"])
    with pytest.raises(TaskFlowDSLError, match="must be independent"):
        compile_taskflow(source)


def test_parallel_group_rejects_different_database_scopes():
    source = load()["taskflow_source"]
    node = next(node for node in source["nodes"] if node["id"] == "n8")
    node["config"]["datasources"] = ["different_database"]
    with pytest.raises(TaskFlowDSLError, match="same datasource"):
        compile_taskflow(source)


@pytest.mark.parametrize(
    "name", ["taskflow-db-fetch-template.json", "taskflow-db-qa-template.json"]
)
def test_existing_serial_templates_still_compile(name):
    flow = json.loads((TEMPLATES / "zh" / name).read_text())["flow"]
    compiled = compile_taskflow(flow["taskflow_source"])
    assert compiled.nodes
