"""Build AWEL DAGs from serialized data."""

import logging
import uuid
from contextlib import suppress
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

from dbgpt._private.pydantic import BaseModel, Field, root_validator, validator
from dbgpt.core.awel.dag.base import DAG, DAGNode

from .base import OperatorType, ResourceMetadata, ViewMetadata, _get_operator_class

logger = logging.getLogger(__name__)


class FlowPositionData(BaseModel):
    """Position of a node in a flow."""

    x: float = Field(
        ..., description="X coordinate of the node", examples=[1081.1, 1000.9]
    )
    y: float = Field(
        ..., description="Y coordinate of the node", examples=[-113.7, -122]
    )
    zoom: float = Field(0, description="Zoom level of the node")


class FlowNodeData(BaseModel):
    """Node data in a flow."""

    width: int = Field(
        ...,
        description="Width of the node",
        examples=[300, 250],
    )
    height: int = Field(..., description="Height of the node", examples=[378, 400])
    id: str = Field(
        ...,
        description="Id of the node",
        examples=[
            "operator_llm_operator___$$___llm___$$___v1_0",
            "resource_dbgpt.model.proxy.llms.chatgpt.OpenAILLMClient_0",
        ],
    )
    position: FlowPositionData = Field(..., description="Position of the node")
    type: Optional[str] = Field(
        default=None,
        description="Type of current UI node(Just for UI)",
        examples=["customNode"],
    )
    data: Union[ViewMetadata, ResourceMetadata] = Field(
        ..., description="Data of the node"
    )
    position_absolute: FlowPositionData = Field(
        ..., description="Absolute position of the node"
    )

    @validator("data", pre=True)
    def parse_data(cls, value: Any):
        """Parse the data."""
        if isinstance(value, dict):
            flow_type = value.get("flow_type")
            if flow_type == "operator":
                return ViewMetadata(**value)
            elif flow_type == "resource":
                return ResourceMetadata(**value)
        raise ValueError("Unable to infer the type for `data`")


class FlowEdgeData(BaseModel):
    """Edge data in a flow."""

    source: str = Field(
        ...,
        description="Source node data id",
        examples=["resource_dbgpt.model.proxy.llms.chatgpt.OpenAILLMClient_0"],
    )
    source_order: int = Field(
        description="The order of the source node in the source node's output",
        examples=[0, 1],
    )
    target: str = Field(
        ...,
        description="Target node data id",
        examples=[
            "operator_llm_operator___$$___llm___$$___v1_0",
        ],
    )
    target_order: int = Field(
        description="The order of the target node in the source node's output",
        examples=[0, 1],
    )
    id: str = Field(..., description="Id of the edge", examples=["edge_0"])
    source_handle: Optional[str] = Field(
        default=None,
        description="Source handle, used in UI",
    )
    target_handle: Optional[str] = Field(
        default=None,
        description="Target handle, used in UI",
    )
    type: Optional[str] = Field(
        default=None,
        description="Type of current UI node(Just for UI)",
        examples=["buttonedge"],
    )

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if (
            "source_order" not in values
            and "source_handle" in values
            and values["source_handle"] is not None
        ):
            with suppress(Exception):
                values["source_order"] = int(values["source_handle"].split("|")[-1])
        if (
            "target_order" not in values
            and "target_handle" in values
            and values["target_handle"] is not None
        ):
            with suppress(Exception):
                values["target_order"] = int(values["target_handle"].split("|")[-1])
        return values


class FlowData(BaseModel):
    """Flow data."""

    nodes: List[FlowNodeData] = Field(..., description="Nodes in the flow")
    edges: List[FlowEdgeData] = Field(..., description="Edges in the flow")
    viewport: FlowPositionData = Field(..., description="Viewport of the flow")


class State(str, Enum):
    """State of a flow panel."""

    INITIALIZING = "initializing"
    DEVELOPING = "developing"
    TESTING = "testing"
    READY_TO_DEPLOY = "ready_to_deploy"
    DEPLOYED = "deployed"
    RUNNING = "running"
    PAUSED = "paused"
    DISABLED = "disabled"
    ENABLED = "enabled"

    @classmethod
    def value_of(cls, value: Optional[str]) -> "State":
        """Get the state by value."""
        if not value:
            return cls.INITIALIZING
        for state in State:
            if state.value == value:
                return state
        raise ValueError(f"Invalid state value: {value}")


class FlowPanel(BaseModel):
    """Flow panel."""

    uid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Flow panel uid",
        examples=[
            "5b25ac8a-ba8e-11ee-b96d-3b9bfdeebd1c",
            "6a4752ae-ba8e-11ee-afff-af8fd9bfe727",
        ],
    )
    name: str = Field(
        ..., description="Flow panel name", examples=["First AWEL Flow", "My LLM Flow"]
    )
    flow_data: FlowData = Field(..., description="Flow data")
    description: Optional[str] = Field(
        None,
        description="Flow panel description",
        examples=["My first AWEL flow"],
    )
    state: State = Field(
        default=State.INITIALIZING, description="Current state of the flow panel"
    )
    source: Optional[str] = Field(
        "DBGPT-WEB",
        description="Source of the flow panel",
        examples=["DB-GPT-WEB", "DBGPT-GITHUB"],
    )
    source_url: Optional[str] = Field(
        None,
        description="Source url of the flow panel",
    )
    version: Optional[str] = Field(
        "0.1.0", description="Version of the flow panel", examples=["0.1.0", "0.2.0"]
    )
    user_name: Optional[str] = Field(None, description="User name")
    sys_code: Optional[str] = Field(None, description="System code")
    dag_id: Optional[str] = Field(None, description="DAG id, Created by AWEL")

    gmt_created: Optional[str] = Field(
        None,
        description="The flow panel created time.",
        examples=["2021-08-01 12:00:00", "2021-08-01 12:00:01", "2021-08-01 12:00:02"],
    )
    gmt_modified: Optional[str] = Field(
        None,
        description="The flow panel modified time.",
        examples=["2021-08-01 12:00:00", "2021-08-01 12:00:01", "2021-08-01 12:00:02"],
    )

    def change_state(self, new_state: State) -> bool:
        """Change the state of the flow panel."""
        allowed_transitions: Dict[State, List[State]] = {
            State.INITIALIZING: [State.DEVELOPING],
            State.DEVELOPING: [State.TESTING, State.DISABLED],
            State.TESTING: [State.READY_TO_DEPLOY, State.DEVELOPING, State.DISABLED],
            State.READY_TO_DEPLOY: [State.DEPLOYED, State.DEVELOPING],
            State.DEPLOYED: [State.RUNNING, State.DISABLED],
            State.RUNNING: [State.PAUSED, State.DISABLED, State.DEPLOYED],
            State.PAUSED: [State.RUNNING, State.DISABLED],
            State.DISABLED: [State.ENABLED],
            State.ENABLED: [s for s in State if s != State.INITIALIZING],
        }
        if new_state in allowed_transitions[self.state]:
            self.state = new_state
            return True
        else:
            logger.error(f"Invalid state transition from {self.state} to {new_state}")
            return False


class FlowFactory:
    """Flow factory."""

    def __init__(self, dag_prefix: str = "flow_dag"):
        """Init the flow factory."""
        self._dag_prefix = dag_prefix

    def build(self, flow_panel: FlowPanel) -> DAG:
        """Build the flow."""
        flow_data = flow_panel.flow_data
        key_to_operator_nodes: Dict[str, FlowNodeData] = {}
        key_to_resource_nodes: Dict[str, FlowNodeData] = {}
        key_to_resource: Dict[str, ResourceMetadata] = {}
        key_to_downstream: Dict[str, List[Tuple[str, int, int]]] = {}
        key_to_upstream: Dict[str, List[Tuple[str, int, int]]] = {}
        for node in flow_data.nodes:
            key = node.id
            if key in key_to_operator_nodes or key in key_to_resource_nodes:
                raise ValueError("Duplicate node key.")
            if node.data.is_operator:
                key_to_operator_nodes[key] = node
            else:
                if not isinstance(node.data, ResourceMetadata):
                    raise ValueError("Node data is not a resource.")
                key_to_resource_nodes[key] = node
                key_to_resource[key] = node.data

        for edge in flow_data.edges:
            source_key = edge.source
            target_key = edge.target
            source_node: FlowNodeData | None = key_to_operator_nodes.get(
                source_key
            ) or key_to_resource_nodes.get(source_key)
            target_node: FlowNodeData | None = key_to_operator_nodes.get(
                target_key
            ) or key_to_resource_nodes.get(target_key)
            if source_node is None or target_node is None:
                raise ValueError("Unable to find source or target node.")
            if source_node.data.is_operator and not target_node.data.is_operator:
                raise ValueError("Unable to connect operator to resource.")
            if not source_node.data.is_operator and not target_node.data.is_operator:
                raise ValueError("Unable to connect resource to resource.")
            if source_node.data.is_operator and target_node.data.is_operator:
                # Operator to operator.
                downstream = key_to_downstream.get(source_key, [])
                downstream.append((target_key, edge.source_order, edge.target_order))
                key_to_downstream[source_key] = downstream

                upstream = key_to_upstream.get(target_key, [])
                upstream.append((source_key, edge.source_order, edge.target_order))
                key_to_upstream[target_key] = upstream
            elif not source_node.data.is_operator and target_node.data.is_operator:
                # Resource to operator.
                target_order = edge.target_order
                has_matched = False
                for i, param in enumerate(target_node.data.parameters):
                    if i == target_order:
                        if param.category != "resource":
                            err_msg = (
                                f"Unable to connect resource to operator, "
                                f"target_order: {target_order}, parameter name: "
                                f"{param.name}, param category: {param.category}"
                            )
                            logger.warning(err_msg)
                            raise ValueError(err_msg)
                        param.value = source_key
                        has_matched = True
                if not has_matched:
                    raise ValueError(
                        "Unable to connect resource to operator, "
                        f"source key: {source_key}, "
                        f"target key: {target_key}, "
                        f"target_order: {target_order}"
                    )

            else:
                raise ValueError("Unable to connect resource to resource.")

        # Sort the keys by the order of the nodes.
        for key, value in key_to_downstream.items():
            # Sort by source_order.
            key_to_downstream[key] = sorted(value, key=lambda x: x[1])
        for key, value in key_to_upstream.items():
            # Sort by target_order.
            key_to_upstream[key] = sorted(value, key=lambda x: x[2])

        key_to_tasks: Dict[str, DAGNode] = {}
        for operator_key, node in key_to_operator_nodes.items():
            if not isinstance(node.data, ViewMetadata):
                raise ValueError("Node data is not a ViewMetadata.")
            view_metadata = node.data
            origin_operator_key = node.data.get_operator_key()
            operator_cls: Type[DAGNode] = _get_operator_class(origin_operator_key)
            # Use metadata from operator class instead of node data(for safety).
            metadata = operator_cls.metadata
            if not metadata:
                raise ValueError("Metadata is not set.")
            if metadata.operator_type == OperatorType.BRANCH:
                # Branch operator, we suppose than the task_name of downstream is the
                # parameter value of the branch operator.
                downstream = key_to_downstream.get(operator_key, [])
                if not downstream:
                    raise ValueError("Branch operator should have downstream.")
                if len(downstream) != len(view_metadata.parameters):
                    raise ValueError(
                        "Branch operator should have the same number of downstream as "
                        "parameters."
                    )
                for i, param in enumerate(view_metadata.parameters):
                    downstream_key, _, _ = downstream[i]
                    param.value = key_to_operator_nodes[downstream_key].data.name

            runnable_params = metadata.get_runnable_parameters(
                view_metadata.parameters, key_to_resource
            )
            runnable_params["task_name"] = metadata.name
            operator_task: DAGNode = cast(DAGNode, operator_cls(**runnable_params))
            key_to_tasks[operator_key] = operator_task

        return self.build_dag(
            flow_panel,
            key_to_tasks,
            key_to_downstream,
            key_to_upstream,
            dag_id=flow_panel.dag_id,
        )

    def build_dag(
        self,
        flow_panel: FlowPanel,
        key_to_tasks: Dict[str, DAGNode],
        key_to_downstream: Dict[str, List[Tuple[str, int, int]]],
        key_to_upstream: Dict[str, List[Tuple[str, int, int]]],
        dag_id: Optional[str] = None,
    ) -> DAG:
        """Build the DAG."""
        formatted_name = flow_panel.name.replace(" ", "_")
        if not dag_id:
            dag_id = f"{self._dag_prefix}_{formatted_name}_{flow_panel.uid}"
        with DAG(dag_id) as dag:
            for key, task in key_to_tasks.items():
                if not task._node_id:
                    task.set_node_id(dag._new_node_id())
                downstream = key_to_downstream.get(key, [])
                upstream = key_to_upstream.get(key, [])
                task._dag = dag
                if not downstream and not upstream:
                    # A single task.
                    dag._append_node(task)
                    continue
                for downstream_key, _, _ in downstream:
                    # Just one direction.
                    downstream_task = key_to_tasks.get(downstream_key)
                    if not downstream_task:
                        raise ValueError(
                            f"Unable to find downstream task by key {downstream_key}."
                        )
                    if not downstream_task._node_id:
                        downstream_task.set_node_id(dag._new_node_id())
                    if downstream_task is None:
                        raise ValueError("Unable to find downstream task.")
                    task >> downstream_task
            return dag
