"""Tests for the TaskFlow DSL, compiler and built-in templates."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

# Populate the AWEL operator registry before compiling.
import dbgpt.core.awel.trigger.http_trigger  # noqa: F401
import dbgpt.core.interface.operators.prompt_operator  # noqa: F401
import dbgpt.core.interface.output_parser  # noqa: F401
import dbgpt_app.operators.datasource  # noqa: F401
import dbgpt_app.operators.llm  # noqa: F401
import dbgpt_app.operators.report  # noqa: F401
import dbgpt_app.operators.taskflow  # noqa: F401
import dbgpt_serve.agent.resource.datasource  # noqa: F401
from dbgpt.core.awel.flow.flow_factory import FlowFactory, FlowPanel
from dbgpt.core.interface.llm import ModelOutput
from dbgpt_app.operators.taskflow import (
    TASKFLOW_STEP_VIS_TAG,
    TFStepMarkerOperator,
    build_step_marker,
    register_step_events,
    strip_step_markers,
    unregister_step_events,
)

from ..taskflow import (
    TaskFlowDSLError,
    compile_taskflow,
    get_node_kind_manifest,
    parse_dsl,
)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates", "zh")

ALL_KINDS = {
    "start",
    "db_query",
    "file_data",
    "ai_analysis",
    "agent",
    "visualize",
    "human_confirm",
    "report",
    "output",
}


def _load_template(name: str) -> dict:
    with open(os.path.join(TEMPLATE_DIR, name)) as f:
        return json.load(f)["flow"]


class TestDSL:
    def test_parse_ok(self):
        dsl = parse_dsl(
            _load_template("taskflow-quick-query-template.json")["taskflow_source"]
        )
        assert dsl.format == "taskflow/1"
        assert [n.kind for n in dsl.nodes] == [
            "start",
            "db_query",
            "ai_analysis",
            "output",
        ]
        assert dsl.edges == [("n1", "n2"), ("n2", "n3"), ("n3", "n4")]

    def test_format_mismatch(self):
        with pytest.raises(TaskFlowDSLError):
            parse_dsl({"format": "taskflow/2", "nodes": [], "edges": []})

    def test_unknown_kind(self):
        with pytest.raises(TaskFlowDSLError, match="Unknown node kind"):
            compile_taskflow(
                {
                    "nodes": [
                        {"id": "n1", "kind": "start"},
                        {"id": "n2", "kind": "magic"},
                        {"id": "n3", "kind": "output"},
                    ],
                    "edges": [["n1", "n2"], ["n2", "n3"]],
                }
            )

    def test_missing_output(self):
        with pytest.raises(TaskFlowDSLError, match="output"):
            compile_taskflow(
                {
                    "nodes": [{"id": "n1", "kind": "start"}],
                    "edges": [],
                }
            )

    def test_cycle(self):
        with pytest.raises(TaskFlowDSLError, match="cycle"):
            compile_taskflow(
                {
                    "nodes": [
                        {"id": "n1", "kind": "start"},
                        {"id": "n2", "kind": "ai_analysis"},
                        {"id": "n3", "kind": "ai_analysis"},
                        {"id": "n4", "kind": "output"},
                    ],
                    "edges": [
                        ["n1", "n2"],
                        ["n2", "n3"],
                        ["n3", "n2"],
                        ["n3", "n4"],
                    ],
                }
            )

    def test_disconnected_node(self):
        with pytest.raises(TaskFlowDSLError, match="not connected"):
            compile_taskflow(
                {
                    "nodes": [
                        {"id": "n1", "kind": "start"},
                        {"id": "n2", "kind": "db_query"},
                        {"id": "n3", "kind": "output"},
                    ],
                    "edges": [["n1", "n3"]],
                }
            )

    def test_db_query_requires_datasource(self):
        with pytest.raises(TaskFlowDSLError, match="datasource"):
            compile_taskflow(
                {
                    "nodes": [
                        {"id": "n1", "kind": "start"},
                        {"id": "n2", "kind": "db_query"},
                        {"id": "n3", "kind": "output"},
                    ],
                    "edges": [["n1", "n2"], ["n2", "n3"]],
                }
            )

    def test_file_data_requires_file(self):
        with pytest.raises(TaskFlowDSLError, match="file_name"):
            compile_taskflow(
                {
                    "nodes": [
                        {"id": "n1", "kind": "start"},
                        {"id": "n2", "kind": "file_data"},
                        {"id": "n3", "kind": "output"},
                    ],
                    "edges": [["n1", "n2"], ["n2", "n3"]],
                }
            )

    def test_file_data_file_id_propagated(self):
        flow_data = compile_taskflow(
            {
                "nodes": [
                    {"id": "n1", "kind": "start"},
                    {
                        "id": "n2",
                        "kind": "file_data",
                        "config": {"file_id": "abc-123", "file_name": "sales.xlsx"},
                    },
                    {"id": "n3", "kind": "output"},
                ],
                "edges": [["n1", "n2"], ["n2", "n3"]],
            }
        )
        file_op = next(n for n in flow_data.nodes if "file_data_operator" in n.id)
        params = {p.name: p.value for p in file_op.data.parameters}
        assert params["file_id"] == "abc-123"
        assert params["file_name"] == "sales.xlsx"


class TestManifest:
    def test_manifest_kinds(self):
        manifest = get_node_kind_manifest()
        assert {m["kind"] for m in manifest} == ALL_KINDS
        for item in manifest:
            assert item["label"] and item["label_en"]
            assert item["group_label"]
            for f in item["config_fields"]:
                assert f["name"] and f["type"] and f["label"] and f["label_en"]

    def test_db_query_fields(self):
        manifest = {m["kind"]: m for m in get_node_kind_manifest()}
        fields = {f["name"]: f for f in manifest["db_query"]["config_fields"]}
        assert fields["datasource"]["required"] is True
        assert fields["datasource"]["type"] == "datasource"
        assert fields["max_rows"]["default"] == 1000


class TestCompileTemplates:
    @pytest.mark.parametrize(
        "template_file,awel_nodes,content_nodes",
        [
            ("taskflow-data-analysis-template.json", 19, 5),
            ("taskflow-quick-query-template.json", 12, 2),
            ("taskflow-excel-analysis-template.json", 9, 3),
            ("taskflow-agent-qa-template.json", 9, 3),
            ("taskflow-agent-db-analysis-template.json", 20, 6),
            ("taskflow-agent-csv-analysis-template.json", 15, 6),
        ],
    )
    def test_compile(self, template_file, awel_nodes, content_nodes):
        flow = _load_template(template_file)
        dsl = parse_dsl(flow["taskflow_source"])
        flow_data = compile_taskflow(dsl)
        assert len(flow_data.nodes) == awel_nodes
        markers = [n for n in flow_data.nodes if "step_marker" in n.id]
        assert len(markers) == content_nodes
        dsl_ids = {n.id for n in dsl.nodes}
        for marker in markers:
            step_param = next(p for p in marker.data.parameters if p.name == "step_id")
            assert step_param.value in dsl_ids

    def test_db_query_wiring(self):
        flow = _load_template("taskflow-data-analysis-template.json")
        flow_data = compile_taskflow(flow["taskflow_source"])
        nodes = {n.id: n for n in flow_data.nodes}

        def find(prefix):
            return next(nid for nid in nodes if nid.startswith(prefix))

        trigger = find("operator_common_llm_http_trigger")
        clock = find("operator_taskflow_step_clock")
        retriever = find("operator_higher_order_datasource_retriever")
        llm = find("operator_higher_order_llm_operator")
        executor = find("operator_higher_order_datasource_executor")
        parser = find("operator_default_sql_output_parser")
        resource = find("resource_dbgpt_serve")

        edge_set = {(e.source, e.target) for e in flow_data.edges}
        # trigger fans out: body -> llm, message -> clock -> retriever
        assert (trigger, llm) in edge_set
        assert (trigger, clock) in edge_set
        assert (clock, retriever) in edge_set
        # text2sql chain
        assert (retriever, llm) in edge_set
        assert (llm, parser) in edge_set
        assert (parser, executor) in edge_set
        # resource injected as parameters
        assert (resource, retriever) in edge_set
        assert (resource, executor) in edge_set

        # max_rows propagated to the retriever
        retriever_node = nodes[retriever]
        max_rows_param = next(
            p for p in retriever_node.data.parameters if p.name == "max_num_results"
        )
        assert max_rows_param.value == 1000
        # datasource db_name propagated
        resource_node = nodes[resource]
        db_name_param = next(
            p for p in resource_node.data.parameters if p.name == "db_name"
        )
        assert db_name_param.value == "case_1_student_manager"

    def test_output_is_last_output_join(self):
        """All markers feed the single output leaf, whose operator emits only
        the previous node's output (marker + content) as the final answer."""
        flow = _load_template("taskflow-data-analysis-template.json")
        flow_data = compile_taskflow(flow["taskflow_source"])
        join = next(n for n in flow_data.nodes if "last_output" in n.id)
        marker_ids = {n.id for n in flow_data.nodes if "step_marker" in n.id}
        join_sources = {e.source for e in flow_data.edges if e.target == join.id}
        assert marker_ids == join_sources

    def test_last_output_operator_emits_previous_node(self):
        from dbgpt_app.operators.taskflow import TFLastOutputOperator

        op = TFLastOutputOperator()
        assert op._last("a", "b", "c") == "c"
        assert op._last("a", "", "b") == "b"
        assert op._last() == ""

    def test_clock_receives_message_and_body(self):
        flow = _load_template("taskflow-data-analysis-template.json")
        flow_data = compile_taskflow(flow["taskflow_source"])
        trigger = next(
            n.id
            for n in flow_data.nodes
            if n.id.startswith("operator_common_llm_http_trigger")
        )
        clock = next(
            n.id
            for n in flow_data.nodes
            if n.id.startswith("operator_taskflow_step_clock")
        )
        edges = [
            e for e in flow_data.edges if e.source == trigger and e.target == clock
        ]
        assert len(edges) == 2
        targets = sorted(e.target_handle for e in edges)
        assert targets == [f"{clock}|inputs|0", f"{clock}|inputs|1"]

    def test_recompile_entity_refreshes_stale_flow_data_in_memory(self):
        """Stale rows get a fresh compile for DAG build; the dao is untouched."""
        from types import SimpleNamespace

        from ..service.service import Service

        flow = _load_template("taskflow-quick-query-template.json")
        entity = SimpleNamespace(
            flow_format="taskflow",
            taskflow_source=json.dumps(flow["taskflow_source"]),
            flow_data=json.dumps({"nodes": [], "edges": [], "viewport": {}}),
            name="quick",
            uid="u1",
        )
        # Bare instance: only the recompile helper is exercised.
        service = Service.__new__(Service)
        service._maybe_recompile_taskflow_entity(entity)
        # The refreshed flow_data is a FlowData pydantic object (what
        # FlowFactory.build expects on FlowPanel-like entities).
        assert hasattr(entity.flow_data, "nodes")
        assert len(entity.flow_data.nodes) == 12

    def test_agent_requires_goal(self):
        with pytest.raises(TaskFlowDSLError, match="goal"):
            compile_taskflow(
                {
                    "nodes": [
                        {"id": "n1", "kind": "start"},
                        {"id": "n2", "kind": "agent"},
                        {"id": "n3", "kind": "output"},
                    ],
                    "edges": [["n1", "n2"], ["n2", "n3"]],
                }
            )

    def test_agent_template_params_propagated(self):
        flow = _load_template("taskflow-agent-qa-template.json")
        flow_data = compile_taskflow(flow["taskflow_source"])
        agents = [n for n in flow_data.nodes if "agent_operator" in n.id]
        assert len(agents) == 3
        first = {p.name: p.value for p in agents[0].data.parameters}
        assert first["agent_profile"] == "react_knowledge"
        assert first["tools"] == ["knowledge_retrieve"]
        assert first["max_turns"] == 8
        assert first["step_id"] == "n2"
        assert first["goal"]

    def test_agent_chained_data_channel(self):
        """Each agent node receives data from ALL prior nodes (fan-out)."""
        flow = _load_template("taskflow-agent-qa-template.json")
        flow_data = compile_taskflow(flow["taskflow_source"])
        agents = [n for n in flow_data.nodes if "agent_operator" in n.id]
        # The 3rd agent (n4) sees answers of both prior agents on its data input.
        n4 = agents[2]
        data_sources = {
            e.source
            for e in flow_data.edges
            if e.target == n4.id and e.target_handle.endswith("inputs|1")
        }
        assert {a.id for a in agents[:2]} == data_sources

    def test_recompile_entity_skips_non_taskflow(self):
        from types import SimpleNamespace

        from ..service.service import Service

        entity = SimpleNamespace(
            flow_format="awel",
            taskflow_source=None,
            flow_data='{"nodes": []}',
            name="awel",
            uid="u2",
        )
        service = Service.__new__(Service)
        service._maybe_recompile_taskflow_entity(entity)
        assert entity.flow_data == '{"nodes": []}'

    def test_excel_template_has_no_datasource_resource(self):
        flow = _load_template("taskflow-excel-analysis-template.json")
        flow_data = compile_taskflow(flow["taskflow_source"])
        resources = [
            n for n in flow_data.nodes if n.id.startswith("resource_dbgpt_serve")
        ]
        assert not resources


class TestStepMarker:
    def test_build_and_strip(self):
        marker = build_step_marker("n2", "数据库查询", "db_query", duration_ms=120)
        assert marker.startswith(f"```{TASKFLOW_STEP_VIS_TAG}")
        assert '"step_id": "n2"' in marker
        assert '"duration_ms": 120' in marker
        text = marker + "real content"
        assert strip_step_markers(text) == "real content"

    def test_strip_without_markers(self):
        assert strip_step_markers("hello") == "hello"
        assert strip_step_markers("") == ""

    @pytest.mark.asyncio
    async def test_marker_operator_map(self):
        op = TFStepMarkerOperator(
            step_id="n3", step_label="智能分析", step_kind="ai_analysis"
        )
        out = await op.map("conclusion text")
        assert TASKFLOW_STEP_VIS_TAG in out
        assert out.endswith("conclusion text")
        payload_line = out.split("```")[1].replace(TASKFLOW_STEP_VIS_TAG, "")
        payload = json.loads(payload_line)
        assert payload["step_id"] == "n3"
        assert payload["kind"] == "ai_analysis"

    @pytest.mark.asyncio
    async def test_marker_pushes_step_event(self):
        op = TFStepMarkerOperator(
            step_id="n3", step_label="智能分析", step_kind="ai_analysis"
        )
        queue = register_step_events("conv-1")
        try:
            with patch.object(
                TFStepMarkerOperator,
                "current_dag_context",
                new_callable=PropertyMock,
            ) as mock_ctx:
                mock_ctx.return_value.get_from_share_data = AsyncMock(
                    return_value="conv-1"
                )
                out = await op.map("结论")
            assert queue.get_nowait() == out
            assert queue.empty()
        finally:
            unregister_step_events("conv-1")

    @pytest.mark.asyncio
    async def test_marker_skips_event_without_queue(self):
        op = TFStepMarkerOperator(
            step_id="n3", step_label="智能分析", step_kind="ai_analysis"
        )
        with patch.object(
            TFStepMarkerOperator, "current_dag_context", new_callable=PropertyMock
        ) as mock_ctx:
            mock_ctx.return_value.get_from_share_data = AsyncMock(
                return_value="conv-not-registered"
            )
            out = await op.map("结论")
        assert "结论" in out


class TestMergeStepEvents:
    @pytest.mark.asyncio
    async def test_passthrough_without_queue(self):
        from ..service.service import _merge_step_events

        async def dag_stream():
            yield ModelOutput(error_code=0, text="A", incremental=False)
            yield ModelOutput(error_code=0, text="B", incremental=False)

        outs = [o async for o in _merge_step_events(dag_stream(), None, False)]
        assert [o.text for o in outs] == ["A", "B"]

    @pytest.mark.asyncio
    async def test_events_arrive_before_final_output(self):
        from ..service.service import _merge_step_events

        queue: "asyncio.Queue[str]" = asyncio.Queue()

        async def dag_stream():
            # The join output only comes after all upstream nodes complete.
            await asyncio.sleep(0.05)
            yield ModelOutput(error_code=0, text="FINAL", incremental=False)

        async def produce():
            await asyncio.sleep(0.01)
            await queue.put("STEP1")

        producer = asyncio.ensure_future(produce())
        outs = [o async for o in _merge_step_events(dag_stream(), queue, False)]
        await producer
        assert [o.text for o in outs] == ["STEP1", "FINAL"]

    @pytest.mark.asyncio
    async def test_events_enqueued_before_join_are_flushed_first(self):
        from ..service.service import _merge_step_events

        queue: "asyncio.Queue[str]" = asyncio.Queue()
        await queue.put("STEP1")
        await queue.put("STEP2")

        async def dag_stream():
            yield ModelOutput(error_code=0, text="FINAL", incremental=False)

        outs = [o async for o in _merge_step_events(dag_stream(), queue, False)]
        assert [o.text for o in outs] == ["STEP1", "STEP2", "FINAL"]


class TestDAGBuild:
    @pytest.fixture(autouse=True)
    def stub_db_manager(self, monkeypatch):
        from dbgpt._private.config import Config
        from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteTempConnector

        class _StubManager:
            def get_connector(self, db_name):
                return SQLiteTempConnector.create_temporary_db()

            def get_db_list(self, user_id=None):
                return [{"db_type": "sqlite", "db_name": "test_db", "comment": "t"}]

        monkeypatch.setattr(
            Config, "local_db_manager", property(lambda self: _StubManager())
        )

    @pytest.mark.parametrize(
        "template_file",
        [
            "taskflow-quick-query-template.json",
            "taskflow-data-analysis-template.json",
            "taskflow-excel-analysis-template.json",
            "taskflow-agent-qa-template.json",
            "taskflow-agent-db-analysis-template.json",
            "taskflow-agent-csv-analysis-template.json",
        ],
    )
    def test_build_dag(self, template_file):
        flow = _load_template(template_file)
        flow_data = compile_taskflow(flow["taskflow_source"])
        panel = FlowPanel(
            label=flow["label"],
            name=flow["name"],
            flow_data=flow_data,
            description=flow["description"],
        )
        dag = FlowFactory().build(panel)
        # chat_flow requires exactly one trigger and one leaf with str output
        assert len(dag.trigger_nodes) == 1
        assert len(dag.leaf_nodes) == 1
        assert dag.leaf_nodes[0].metadata.outputs[0].type_cls.endswith("str")
