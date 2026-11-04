"""TaskFlow DSL compiler: product DSL (taskflow/1) -> AWEL FlowData.

The compiler expands every product node into a subgraph of AWEL operators
(cloned from the operator registry, so the compiled flow is always consistent
with what :class:`~dbgpt.core.awel.flow.flow_factory.FlowFactory` expects),
then wires the subgraphs with semantic edges:

- ``start`` (CommonLLMHttpTrigger) fans out the request body and the user
  message to the nodes that need them;
- *data channels* connect clean upstream data exits (markdown tables,
  conclusions) to downstream LLM consumers;
- *control edges* preserve the declared chain order for non-data nodes
  (e.g. human confirm);
- every product node's *view* output passes a ``TFStepMarkerOperator`` and is
  collected into the final ``output`` join in chain order, so the chat UI can
  render an ordered step trace from the final answer text.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from dbgpt._private.config import Config
from dbgpt.core.awel.flow.base import (
    _OPERATOR_REGISTRY,
)
from dbgpt.core.awel.flow.flow_factory import (
    FlowData,
    FlowEdgeData,
    FlowNodeData,
    FlowPositionData,
)

from .dsl import (
    TaskFlowDSL,
    TaskFlowDSLError,
    TaskFlowNodeModel,
    parse_dsl,
    topo_order,
    validate_dsl,
)
from .nodes import NODE_KINDS

logger = logging.getLogger(__name__)

CFG = Config()

# ---------------------------------------------------------------------------
# Operator / resource registry keys (metadata ids in _OPERATOR_REGISTRY)
# ---------------------------------------------------------------------------
KEY_TRIGGER = "operator_common_llm_http_trigger___$$___trigger___$$___v1"
KEY_RETRIEVER = (
    "operator_higher_order_datasource_retriever_operator___$$___database___$$___v1"
)
KEY_HO_LLM = "operator_higher_order_llm_operator___$$___llm___$$___v1"
KEY_SQL_PARSER = "operator_default_sql_output_parser___$$___output_parser___$$___v1"
KEY_EXECUTOR = (
    "operator_higher_order_datasource_executor_operator___$$___database___$$___v1"
)
KEY_REPORT = "operator_report_analyst___$$___database___$$___v1"
KEY_JOIN = "operator_taskflow_last_output_operator___$$___common___$$___v1"
KEY_MARKER = "operator_taskflow_step_marker_operator___$$___common___$$___v1"
KEY_FILE = "operator_taskflow_file_data_operator___$$___database___$$___v1"
KEY_ANALYSIS = "operator_taskflow_data_analysis_operator___$$___database___$$___v1"
KEY_AGENT = "operator_taskflow_agent_operator___$$___llm___$$___v1"
KEY_CHART = "operator_taskflow_chart_advisor_operator___$$___database___$$___v1"
KEY_CONFIRM = "operator_taskflow_human_confirm_operator___$$___common___$$___v1"
KEY_CLOCK = "operator_taskflow_step_clock_operator___$$___common___$$___v1"
RES_DATASOURCE = "resource_dbgpt_serve.agent.resource.datasource.DatasourceResource"
RES_PROMPT = (
    "resource_dbgpt.core.interface.operators.prompt_operator.CommonChatPromptTemplate"
)

_PROMPT_SYSTEM_MESSAGE_EN = (
    '{context}\n\nwhen answering, use the same language as the "user".'
)
_PROMPT_SYSTEM_MESSAGE_ZH = "{context}\n\n回答时请使用与用户相同的语言。"


def _ensure_operator_modules() -> None:
    """Import the operator/resource modules the compiler clones metadata from.

    Compilation happens on several paths (create/update, template
    instantiation, boot-time recompile), each with a different import order;
    importing lazily here makes the compiler self-sufficient instead of
    depending on whichever request happened to load the modules first.
    """
    import dbgpt.core.awel.trigger.http_trigger  # noqa: F401
    import dbgpt.core.interface.operators.prompt_operator  # noqa: F401
    import dbgpt.core.interface.output_parser  # noqa: F401
    import dbgpt_app.operators.datasource  # noqa: F401
    import dbgpt_app.operators.llm  # noqa: F401
    import dbgpt_app.operators.report  # noqa: F401
    import dbgpt_app.operators.taskflow  # noqa: F401
    import dbgpt_app.operators.taskflow_agent  # noqa: F401
    import dbgpt_serve.agent.resource.datasource  # noqa: F401


@dataclass
class Port:
    """A connection point of a compiled subgraph."""

    node_id: str
    section: str  # outputs | inputs | parameters
    order: int


@dataclass
class Subgraph:
    """The compiled result of one TaskFlow DSL node."""

    nodes: List[FlowNodeData] = field(default_factory=list)
    edges: List[FlowEdgeData] = field(default_factory=list)
    # Inputs to be wired by the compiler (semantic wiring).
    entry_data: List[Port] = field(default_factory=list)
    entry_question: List[Port] = field(default_factory=list)
    entry_body: List[Port] = field(default_factory=list)
    entry_control: List[Port] = field(default_factory=list)
    # Clean data exits (safe to feed downstream LLM consumers).
    exit_data: List[Port] = field(default_factory=list)
    # Marked view port collected into the final join (chain order).
    join_port: Optional[Port] = None
    # Only for the start node.
    exit_body: Optional[Port] = None
    exit_msg: Optional[Port] = None


class TaskFlowCompiler:
    """Compile a TaskFlow DSL document into an AWEL FlowData."""

    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._nodes: List[FlowNodeData] = []
        self._edges: List[FlowEdgeData] = []
        self._edge_ids = set()
        self._col = 0

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def compile(self, source: Union[Dict[str, Any], TaskFlowDSL]) -> FlowData:
        """Compile the DSL and return the AWEL FlowData."""
        dsl = source if isinstance(source, TaskFlowDSL) else parse_dsl(source)
        validate_dsl(dsl, NODE_KINDS)
        node_map = {n.id: n for n in dsl.nodes}
        order = topo_order(dsl)
        predecessors: Dict[str, List[str]] = {n.id: [] for n in dsl.nodes}
        for src, tgt in dsl.edges:
            predecessors[tgt].append(src)

        subgraphs: Dict[str, Subgraph] = {}
        for index, node_id in enumerate(order):
            self._col = index
            node = node_map[node_id]
            upstreams = [subgraphs[u] for u in predecessors[node_id]]
            subgraphs[node_id] = self._build(node, upstreams)

        start_id = next(nid for nid in order if node_map[nid].kind == "start")
        trigger = subgraphs[start_id]

        for index, node_id in enumerate(order):
            node = node_map[node_id]
            if node.kind == "start":
                continue
            sg = subgraphs[node_id]
            for port in sg.entry_question:
                self._connect(trigger.exit_msg, port)
            for port in sg.entry_body:
                self._connect(trigger.exit_body, port)
            for port in sg.entry_control:
                for up in [subgraphs[u] for u in predecessors[node_id]]:
                    source = up.exit_data[0] if up.exit_data else up.join_port
                    if source:
                        self._connect(source, port)
            if node.kind == "output":
                continue
            # Data entries: every clean data exit of the PRIOR nodes.
            for entry in sg.entry_data:
                for prior_id in order[:index]:
                    for data_port in subgraphs[prior_id].exit_data:
                        self._connect(data_port, entry)

        output_ids = [nid for nid in order if node_map[nid].kind == "output"]
        if output_ids:
            join_entry = subgraphs[output_ids[0]].entry_data[0]
            # All step markers stay wired into the single output leaf (the
            # DAG requires one leaf); the TFLastOutputOperator itself emits
            # only the previous node's output as the final answer.
            for node_id in order:
                join_port = subgraphs[node_id].join_port
                if join_port:
                    self._connect(join_port, join_entry)

        return FlowData(
            nodes=self._nodes,
            edges=self._edges,
            viewport=FlowPositionData(x=0, y=0, zoom=0.8),
        )

    # ------------------------------------------------------------------
    # metadata / node / edge helpers
    # ------------------------------------------------------------------
    def _clone_metadata(self, key: str):
        item = _OPERATOR_REGISTRY.get_registry_item(key)
        if not item:
            _ensure_operator_modules()
            item = _OPERATOR_REGISTRY.get_registry_item(key)
        if not item:
            raise TaskFlowDSLError(
                f"AWEL operator/resource not registered: {key}. Make sure the "
                "corresponding module is imported before compiling."
            )
        return item.metadata.model_copy(deep=True)

    def _new_id(self, key: str) -> str:
        count = self._counters.get(key, 0)
        self._counters[key] = count + 1
        return f"{key}_{count}"

    def _position(self, row: int):
        x = 120 + self._col * 340
        y = 120 + row * 160 + (self._col % 2) * 24
        return FlowPositionData(x=x, y=y, zoom=0)

    def _add_node(
        self,
        key: str,
        row: int,
        params: Optional[Dict[str, Any]] = None,
        step: Optional[TaskFlowNodeModel] = None,
    ) -> str:
        meta = self._clone_metadata(key)
        node_id = self._new_id(key)
        meta.id = node_id
        # Dynamic options are resolved against the runtime environment and are
        # only needed by the legacy AWEL canvas; drop them so compilation is
        # hermetic and the compiled flow_data stays lean.
        for param in meta.parameters:
            param.options = None
        if params:
            name_to_param = {p.name: p for p in meta.parameters}
            for pname, value in params.items():
                if value is None:
                    continue
                target = name_to_param.get(pname)
                if target is None:
                    raise TaskFlowDSLError(
                        f"Parameter {pname} not found in metadata of {key}"
                    )
                target.value = value
        if step:
            meta.custom_label = step.label or NODE_KINDS[step.kind].label
        position = self._position(row)
        self._nodes.append(
            FlowNodeData(
                width=300,
                height=160,
                id=node_id,
                position=position,
                type="customNode",
                data=meta.to_dict(),
                position_absolute=position.model_copy(),
            )
        )
        return node_id

    def _connect(self, source: Port, target: Port):
        if source is None or target is None:
            return
        edge_id = f"{source.node_id}|{target.node_id}"
        base, i = edge_id, 1
        while edge_id in self._edge_ids:
            edge_id = f"{base}_{i}"
            i += 1
        self._edge_ids.add(edge_id)
        self._edges.append(
            FlowEdgeData(
                id=edge_id,
                source=source.node_id,
                target=target.node_id,
                source_order=source.order,
                target_order=target.order,
                source_handle=f"{source.node_id}|{source.section}|{source.order}",
                target_handle=f"{target.node_id}|{target.section}|{target.order}",
                type="buttonedge",
            )
        )

    @staticmethod
    def _param_order(meta, name: str) -> int:
        for i, p in enumerate(meta.parameters):
            if p.name == name:
                return i
        raise TaskFlowDSLError(f"Parameter {name} not found in metadata")

    def _add_marker(self, node: TaskFlowNodeModel, row: int) -> str:
        spec = NODE_KINDS[node.kind]
        return self._add_node(
            KEY_MARKER,
            row,
            params={
                "step_id": node.id,
                "step_label": node.label or spec.label,
                "step_kind": node.kind,
            },
        )

    # ------------------------------------------------------------------
    # per-kind builders
    # ------------------------------------------------------------------
    def _build(self, node: TaskFlowNodeModel, upstreams: List[Subgraph]) -> Subgraph:
        builder = getattr(self, f"_build_{node.kind}", None)
        if builder is None:
            raise TaskFlowDSLError(f"No compiler builder for kind: {node.kind}")
        return builder(node, upstreams)

    def _build_start(self, node: TaskFlowNodeModel, _) -> Subgraph:
        trigger = self._add_node(
            KEY_TRIGGER, 0, params={"endpoint": "/taskflow/{dag_id}"}, step=node
        )
        # The clock records the flow start timestamp; all user-message inputs
        # are routed through it so the first step duration is measured from
        # the actual start of the run. The request body feeds the clock's
        # second input so the conv_uid reaches step markers (live events).
        clock = self._add_node(KEY_CLOCK, 1)
        self._connect(Port(trigger, "outputs", 1), Port(clock, "inputs", 0))
        self._connect(Port(trigger, "outputs", 0), Port(clock, "inputs", 1))
        return Subgraph(
            exit_body=Port(trigger, "outputs", 0),
            exit_msg=Port(clock, "outputs", 0),
        )

    def _build_db_query(self, node: TaskFlowNodeModel, _) -> Subgraph:
        config = node.config
        datasource = config.get("datasource")
        if not datasource:
            raise TaskFlowDSLError(
                f"Node {node.id} (db_query) requires config.datasource"
            )
        resource = self._add_node(
            RES_DATASOURCE,
            0,
            params={"name": "datasource", "db_name": datasource},
        )
        retriever = self._add_node(
            KEY_RETRIEVER,
            1,
            params={"max_num_results": int(config.get("max_rows") or 1000)},
            step=node,
        )
        prompt = self._add_node(
            RES_PROMPT,
            2,
            params={
                "system_message": (
                    _PROMPT_SYSTEM_MESSAGE_ZH
                    if CFG.LANGUAGE == "zh"
                    else _PROMPT_SYSTEM_MESSAGE_EN
                )
            },
        )
        llm = self._add_node(KEY_HO_LLM, 3)
        parser = self._add_node(KEY_SQL_PARSER, 4)
        executor = self._add_node(KEY_EXECUTOR, 5)
        marker = self._add_marker(node, 6)

        self._connect(
            Port(resource, "outputs", 0),
            Port(
                retriever,
                "parameters",
                self._param_order(self._clone_metadata(KEY_RETRIEVER), "datasource"),
            ),
        )
        self._connect(
            Port(resource, "outputs", 0),
            Port(
                executor,
                "parameters",
                self._param_order(self._clone_metadata(KEY_EXECUTOR), "datasource"),
            ),
        )
        self._connect(
            Port(prompt, "outputs", 0),
            Port(
                llm,
                "parameters",
                self._param_order(self._clone_metadata(KEY_HO_LLM), "prompt_template"),
            ),
        )
        self._connect(Port(retriever, "outputs", 0), Port(llm, "inputs", 1))
        self._connect(Port(llm, "outputs", 0), Port(parser, "inputs", 0))
        self._connect(Port(parser, "outputs", 0), Port(executor, "inputs", 0))
        self._connect(Port(executor, "outputs", 0), Port(marker, "inputs", 0))

        return Subgraph(
            entry_body=[Port(llm, "inputs", 0)],
            entry_question=[Port(retriever, "inputs", 0)],
            exit_data=[Port(executor, "outputs", 1)],
            join_port=Port(marker, "outputs", 0),
        )

    def _build_file_data(self, node: TaskFlowNodeModel, _) -> Subgraph:
        config = node.config
        file_name = config.get("file_name")
        file_id = config.get("file_id")
        if not file_name and not file_id:
            raise TaskFlowDSLError(
                f"Node {node.id} (file_data) requires config.file_name or "
                "config.file_id"
            )
        file_op = self._add_node(
            KEY_FILE,
            0,
            params={
                "file_name": file_name,
                "file_id": file_id,
                "max_rows": int(config.get("max_rows") or 1000),
            },
            step=node,
        )
        marker = self._add_marker(node, 1)
        self._connect(Port(file_op, "outputs", 0), Port(marker, "inputs", 0))
        return Subgraph(
            entry_question=[Port(file_op, "inputs", 0)],
            exit_data=[Port(file_op, "outputs", 0)],
            join_port=Port(marker, "outputs", 0),
        )

    def _build_ai_analysis(self, node: TaskFlowNodeModel, _) -> Subgraph:
        config = node.config
        analysis = self._add_node(
            KEY_ANALYSIS,
            0,
            params={
                "model": config.get("model"),
                "analysis_prompt": config.get("analysis_prompt"),
            },
            step=node,
        )
        marker = self._add_marker(node, 1)
        self._connect(Port(analysis, "outputs", 0), Port(marker, "inputs", 0))
        return Subgraph(
            entry_question=[Port(analysis, "inputs", 0)],
            entry_data=[Port(analysis, "inputs", 1)],
            exit_data=[Port(analysis, "outputs", 0)],
            join_port=Port(marker, "outputs", 0),
        )

    def _build_agent(self, node: TaskFlowNodeModel, _) -> Subgraph:
        config = node.config
        if not (config.get("goal") or "").strip():
            raise TaskFlowDSLError(f"Node {node.id} (agent) requires config.goal")

        def _list(name: str):
            value = config.get(name)
            if isinstance(value, list):
                return [str(v) for v in value if str(v).strip()]
            if isinstance(value, str) and value.strip():
                return [v.strip() for v in value.splitlines() if v.strip()]
            return None

        agent = self._add_node(
            KEY_AGENT,
            0,
            params={
                "agent_profile": config.get("agent_profile"),
                "goal": config.get("goal"),
                "model": config.get("model"),
                "tools": _list("tools"),
                "skills": _list("skills"),
                "datasources": _list("datasources"),
                "knowledge": _list("knowledge"),
                "mcp": _list("mcp"),
                "max_turns": int(config.get("max_turns") or 10),
                "step_id": node.id,
                "step_label": node.label or NODE_KINDS[node.kind].label,
            },
            step=node,
        )
        marker = self._add_marker(node, 1)
        self._connect(Port(agent, "outputs", 0), Port(marker, "inputs", 0))
        return Subgraph(
            entry_question=[Port(agent, "inputs", 0)],
            entry_data=[Port(agent, "inputs", 1)],
            exit_data=[Port(agent, "outputs", 0)],
            join_port=Port(marker, "outputs", 0),
        )

    def _build_visualize(self, node: TaskFlowNodeModel, _) -> Subgraph:
        config = node.config
        params: Dict[str, Any] = {
            "model": config.get("model"),
            "max_charts": int(config.get("max_charts") or 4),
        }
        chart = self._add_node(KEY_CHART, 0, params=params, step=node)
        datasource = config.get("datasource")
        if datasource:
            resource = self._add_node(
                RES_DATASOURCE,
                1,
                params={"name": "datasource", "db_name": datasource},
            )
            self._connect(
                Port(resource, "outputs", 0),
                Port(
                    chart,
                    "parameters",
                    self._param_order(self._clone_metadata(KEY_CHART), "datasource"),
                ),
            )
        marker = self._add_marker(node, 2)
        self._connect(Port(chart, "outputs", 0), Port(marker, "inputs", 0))
        return Subgraph(
            entry_question=[Port(chart, "inputs", 0)],
            entry_data=[Port(chart, "inputs", 1)],
            join_port=Port(marker, "outputs", 0),
        )

    def _build_human_confirm(self, node: TaskFlowNodeModel, _) -> Subgraph:
        config = node.config
        confirm = self._add_node(
            KEY_CONFIRM,
            0,
            params={"message": config.get("message")},
            step=node,
        )
        marker = self._add_marker(node, 1)
        self._connect(Port(confirm, "outputs", 0), Port(marker, "inputs", 0))
        return Subgraph(
            entry_control=[Port(confirm, "inputs", 0)],
            exit_data=[Port(confirm, "outputs", 0)],
            join_port=Port(marker, "outputs", 0),
        )

    def _build_report(self, node: TaskFlowNodeModel, _) -> Subgraph:
        config = node.config
        report = self._add_node(
            KEY_REPORT, 0, params={"model": config.get("model")}, step=node
        )
        marker = self._add_marker(node, 1)
        self._connect(Port(report, "outputs", 0), Port(marker, "inputs", 0))
        return Subgraph(
            entry_question=[Port(report, "inputs", 0)],
            entry_data=[Port(report, "inputs", 1)],
            exit_data=[Port(report, "outputs", 0)],
            join_port=Port(marker, "outputs", 0),
        )

    def _build_output(self, node: TaskFlowNodeModel, _) -> Subgraph:
        join = self._add_node(KEY_JOIN, 0, step=node)
        return Subgraph(
            entry_data=[Port(join, "inputs", 0)],
            exit_data=[Port(join, "outputs", 0)],
        )


def compile_taskflow(source: Union[Dict[str, Any], TaskFlowDSL]) -> FlowData:
    """Compile a TaskFlow DSL document into an AWEL FlowData."""
    return TaskFlowCompiler().compile(source)
