"""Build AWEL DAGs from serialized data."""

import logging
import uuid
from contextlib import suppress
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type, Union, cast

from typing_extensions import Annotated

from dbgpt._private.pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    WithJsonSchema,
    field_validator,
    model_to_dict,
    model_validator,
)
from dbgpt.core.awel.dag.base import DAG, DAGNode

from .base import (
    OperatorType,
    ResourceMetadata,
    ResourceType,
    ViewMetadata,
    _get_operator_class,
    _get_resource_class,
)
from .compat import get_new_class_name
from .exceptions import (
    FlowClassMetadataException,
    FlowDAGMetadataException,
    FlowException,
    FlowMetadataException,
)

logger = logging.getLogger(__name__)


AWEL_FLOW_VERSION = "0.1.1"


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

    @field_validator("data", mode="before")
    @classmethod
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

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if not isinstance(values, dict):
            return values
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
    DEPLOYED = "deployed"
    RUNNING = "running"
    DISABLED = "disabled"
    LOAD_FAILED = "load_failed"

    @classmethod
    def value_of(cls, value: Optional[str]) -> "State":
        """Get the state by value."""
        if not value:
            return cls.INITIALIZING
        for state in State:
            if state.value == value:
                return state
        raise ValueError(f"Invalid state value: {value}")

    @classmethod
    def can_change_state(cls, current_state: "State", new_state: "State") -> bool:
        """Change the state of the flow panel."""
        allowed_transitions: Dict[State, List[State]] = {
            State.INITIALIZING: [
                State.DEVELOPING,
                State.INITIALIZING,
                State.LOAD_FAILED,
            ],
            State.DEVELOPING: [
                State.TESTING,
                State.DEPLOYED,
                State.DISABLED,
                State.DEVELOPING,
                State.LOAD_FAILED,
            ],
            State.TESTING: [
                State.TESTING,
                State.DEPLOYED,
                State.DEVELOPING,
                State.DISABLED,
                State.RUNNING,
                State.LOAD_FAILED,
            ],
            State.DEPLOYED: [
                State.DEPLOYED,
                State.DEVELOPING,
                State.TESTING,
                State.DISABLED,
                State.RUNNING,
                State.LOAD_FAILED,
            ],
            State.RUNNING: [
                State.RUNNING,
                State.DEPLOYED,
                State.TESTING,
                State.DISABLED,
            ],
            State.DISABLED: [State.DISABLED, State.DEPLOYED],
            State.LOAD_FAILED: [
                State.LOAD_FAILED,
                State.DEVELOPING,
                State.DEPLOYED,
                State.DISABLED,
            ],
        }
        if new_state in allowed_transitions[current_state]:
            return True
        else:
            logger.error(
                f"Invalid state transition from {current_state} to {new_state}"
            )
            return False


class FlowCategory(str, Enum):
    """Flow category."""

    COMMON = "common"
    CHAT_FLOW = "chat_flow"
    CHAT_AGENT = "chat_agent"

    @classmethod
    def value_of(cls, value: Optional[str]) -> "FlowCategory":
        """Get the flow category by value."""
        if not value:
            return cls.COMMON
        for category in FlowCategory:
            if category.value == value:
                return category
        raise ValueError(f"Invalid flow category value: {value}")


_DAGModel = Annotated[
    DAG,
    WithJsonSchema(
        {
            "type": "object",
            "properties": {
                "task_name": {"type": "string", "description": "Dummy task name"}
            },
            "description": "DAG model, not used in the serialization.",
        }
    ),
]


class FlowPanel(BaseModel):
    """Flow panel."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True, json_encoders={DAG: lambda v: None}
    )

    uid: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Flow panel uid",
        examples=[
            "5b25ac8a-ba8e-11ee-b96d-3b9bfdeebd1c",
            "6a4752ae-ba8e-11ee-afff-af8fd9bfe727",
        ],
    )
    label: str = Field(
        ..., description="Flow panel label", examples=["First AWEL Flow", "My LLM Flow"]
    )
    name: str = Field(
        ..., description="Flow panel name", examples=["first_awel_flow", "my_llm_flow"]
    )
    flow_category: Optional[FlowCategory] = Field(
        default=FlowCategory.COMMON,
        description="Flow category",
        examples=[FlowCategory.COMMON, FlowCategory.CHAT_AGENT],
    )
    flow_data: Optional[FlowData] = Field(None, description="Flow data")
    flow_dag: Optional[_DAGModel] = Field(None, description="Flow DAG", exclude=True)
    description: Optional[str] = Field(
        None,
        description="Flow panel description",
        examples=["My first AWEL flow"],
    )
    state: State = Field(
        default=State.INITIALIZING, description="Current state of the flow panel"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message of load the flow panel",
        examples=["Unable to load the flow panel."],
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
        AWEL_FLOW_VERSION,
        description="Version of the flow panel",
        examples=["0.1.0", "0.2.0"],
    )
    define_type: Optional[str] = Field(
        "json",
        description="Define type of the flow panel",
        examples=["json", "python"],
    )
    editable: bool = Field(
        True,
        description="Whether the flow panel is editable",
        examples=[True, False],
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

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if not isinstance(values, dict):
            return values
        label = values.get("label")
        name = values.get("name")
        flow_category = str(values.get("flow_category", ""))
        if not label and name:
            values["label"] = name
            name = name.replace(" ", "_")
            if flow_category:
                name = str(flow_category) + "_" + name
            values["name"] = name
        return values

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return model_to_dict(self, exclude={"flow_dag"})


class FlowFactory:
    """Flow factory."""

    def __init__(self, dag_prefix: str = "flow_dag"):
        """Init the flow factory."""
        self._dag_prefix = dag_prefix

    def build(self, flow_panel: FlowPanel) -> DAG:
        """Build the flow."""
        if not flow_panel.flow_data:
            raise ValueError("Flow data is required.")
        flow_data = cast(FlowData, flow_panel.flow_data)
        key_to_operator_nodes: Dict[str, FlowNodeData] = {}
        key_to_resource_nodes: Dict[str, FlowNodeData] = {}
        key_to_resource: Dict[str, ResourceMetadata] = {}
        key_to_downstream: Dict[str, List[Tuple[str, int, int]]] = {}
        key_to_upstream: Dict[str, List[Tuple[str, int, int]]] = {}
        key_to_upstream_node: Dict[str, List[FlowNodeData]] = {}
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

            current_upstream = key_to_upstream_node.get(target_key, [])
            current_upstream.append(source_node)
            key_to_upstream_node[target_key] = current_upstream

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
            elif not source_node.data.is_operator and not target_node.data.is_operator:
                # Resource to resource.
                target_order = edge.target_order
                has_matched = False
                for i, param in enumerate(target_node.data.parameters):
                    if i == target_order:
                        if param.category != "resource":
                            err_msg = (
                                f"Unable to connect resource to resource, "
                                f"target_order: {target_order}, parameter name: "
                                f"{param.name}, param category: {param.category}"
                            )
                            logger.warning(err_msg)
                            raise ValueError(err_msg)
                        param.value = source_key
                        has_matched = True
                if not has_matched:
                    raise ValueError(
                        "Unable to connect resource to resource, "
                        f"source key: {source_key}, "
                        f"target key: {target_key}, "
                        f"target_order: {target_order}"
                    )
            else:
                # Operator to resource.
                raise ValueError("Unable to connect operator to resource.")

        # Topological sort
        key_to_order: Dict[str, int] = _topological_sort(key_to_upstream_node)

        # Sort the keys by the order of the nodes.
        for key, value in key_to_downstream.items():
            # Sort by source_order.
            key_to_downstream[key] = sorted(value, key=lambda x: x[1])
        for key, value in key_to_upstream.items():
            # Sort by target_order.
            key_to_upstream[key] = sorted(value, key=lambda x: x[2])

        sorted_key_to_resource_nodes = list(key_to_resource_nodes.values())
        sorted_key_to_resource_nodes = sorted(
            sorted_key_to_resource_nodes,
            key=lambda r: key_to_order[r.id] if r.id in key_to_order else r.id,
        )

        key_to_resource_instance: Dict[str, Any] = {}
        # Build Resources instances as topological order, make sure the dependency
        # resources is built before the children resources.
        for resource_node in sorted_key_to_resource_nodes:
            resource_key = resource_node.id
            if not isinstance(resource_node.data, ResourceMetadata):
                raise ValueError("Node data is not a ResourceMetadata.")
            resource_metadata: ResourceMetadata = resource_node.data
            origin_resource_key = resource_node.data.get_origin_id()
            registered_item = _get_resource_class(origin_resource_key)
            # Use metadata from resource class instead of node data(for safety).
            registered_resource_metadata: ResourceMetadata = registered_item.metadata
            resource_cls = registered_item.cls
            if not registered_resource_metadata:
                raise ValueError("Metadata is not set.")
            if not resource_cls:
                raise ValueError("Resource class is not set.")
            try:
                runnable_params = registered_resource_metadata.get_runnable_parameters(
                    resource_metadata.parameters,
                    key_to_resource,
                    key_to_resource_instance,
                )
                if registered_resource_metadata.resource_type == ResourceType.INSTANCE:
                    key_to_resource_instance[resource_key] = resource_cls(
                        **runnable_params
                    )
                else:
                    # Just use the resource class.
                    key_to_resource_instance[resource_key] = resource_cls
            except FlowMetadataException as e:
                raise e
            except Exception as e:
                raise FlowMetadataException(
                    f"Unable to build resource instance: {resource_key}, resource_cls: "
                    f"{resource_cls}, error: {e}"
                )

        # Build Operators
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

            try:
                runnable_params = metadata.get_runnable_parameters(
                    view_metadata.parameters, key_to_resource, key_to_resource_instance
                )
                runnable_params["task_name"] = operator_key
                operator_task: DAGNode = cast(DAGNode, operator_cls(**runnable_params))
                key_to_tasks[operator_key] = operator_task
            except FlowMetadataException as e:
                raise e
            except Exception as e:
                raise FlowMetadataException(
                    f"Unable to build operator task: {operator_key}, "
                    f"operator_cls: {operator_cls}, error: {e}"
                )

        try:
            return self.build_dag(
                flow_panel,
                key_to_tasks,
                key_to_downstream,
                key_to_upstream,
                dag_id=flow_panel.dag_id,
            )
        except Exception as e:
            raise FlowDAGMetadataException(
                f"Unable to build DAG for flow panel: {flow_panel.name}, error: {e}"
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

                # This upstream has been sorted according to the order in the downstream
                # So we just need to connect the task to the upstream.
                for upstream_key, _, _ in upstream:
                    # Just one direction.
                    upstream_task = key_to_tasks.get(upstream_key)
                    if not upstream_task:
                        raise ValueError(
                            f"Unable to find upstream task by key {upstream_key}."
                        )
                    if not upstream_task._node_id:
                        upstream_task.set_node_id(dag._new_node_id())
                    if upstream_task is None:
                        raise ValueError("Unable to find upstream task.")
                    upstream_task >> task
            return dag

    def pre_load_requirements(self, flow_panel: FlowPanel):
        """Pre load requirements for the flow panel.

        Args:
            flow_panel (FlowPanel): The flow panel
        """
        from dbgpt.util.module_utils import import_from_string

        if not flow_panel.flow_data:
            return

        flow_data = cast(FlowData, flow_panel.flow_data)
        for node in flow_data.nodes:
            if node.data.is_operator:
                node_data = cast(ViewMetadata, node.data)
            else:
                node_data = cast(ResourceMetadata, node.data)
            if not node_data.type_cls:
                continue
            try:
                metadata_cls = import_from_string(node_data.type_cls)
                logger.debug(
                    f"Import {node_data.type_cls} successfully, metadata_cls is : "
                    f"{metadata_cls}"
                )
            except ImportError as e:
                raise_error = True
                new_type_cls: Optional[str] = None
                try:
                    new_type_cls = get_new_class_name(node_data.type_cls)
                    if new_type_cls:
                        metadata_cls = import_from_string(new_type_cls)
                        logger.info(
                            f"Import {new_type_cls} successfully, metadata_cls is : "
                            f"{metadata_cls}"
                        )
                        raise_error = False
                except ImportError as ex:
                    raise FlowClassMetadataException(
                        f"Import {node_data.type_cls} with new type {new_type_cls} "
                        f"failed: {ex}"
                    )
                if raise_error:
                    raise FlowClassMetadataException(
                        f"Import {node_data.type_cls} failed: {e}"
                    )


def _topological_sort(
    key_to_upstream_node: Dict[str, List[FlowNodeData]]
) -> Dict[str, int]:
    """Topological sort.

    Returns the topological order of the nodes and checks if the graph has at least
    one cycle.

    Args:
        key_to_upstream_node (Dict[str, List[FlowNodeData]]): The upstream nodes

    Returns:
        Dict[str, int]: The topological order of the nodes

    Raises:
        ValueError: Graph has at least one cycle
    """
    from collections import deque

    key_to_order: Dict[str, int] = {}
    current_order = 0

    keys = set()
    for key, upstreams in key_to_upstream_node.items():
        keys.add(key)
        for upstream in upstreams:
            keys.add(upstream.id)

    in_degree = {key: 0 for key in keys}
    # Build key to downstream graph.
    graph: Dict[str, List[str]] = {key: [] for key in keys}
    for key in key_to_upstream_node:
        for node in key_to_upstream_node[key]:
            graph[node.id].append(key)
            in_degree[key] += 1

    # Find all nodes with in-degree 0.
    queue = deque([key for key, degree in in_degree.items() if degree == 0])
    while queue:
        current_key: str = queue.popleft()
        key_to_order[current_key] = current_order
        current_order += 1

        for adjacent in graph[current_key]:
            # for each adjacent node, remove the edge from the graph and update the
            # in-degree
            in_degree[adjacent] -= 1
            if in_degree[adjacent] == 0:
                queue.append(adjacent)

    if current_order != len(keys):
        raise ValueError("Graph has at least one cycle")

    return key_to_order


def fill_flow_panel(flow_panel: FlowPanel):
    """Fill the flow panel with the latest metadata.

    Args:
        flow_panel (FlowPanel): The flow panel to fill.
    """
    if not flow_panel.flow_data:
        return
    for node in flow_panel.flow_data.nodes:
        try:
            parameters_map = {}
            if node.data.is_operator:
                data = cast(ViewMetadata, node.data)
                key = data.get_operator_key()
                operator_cls: Type[DAGNode] = _get_operator_class(key)
                metadata = operator_cls.metadata
                if not metadata:
                    raise ValueError("Metadata is not set.")
                input_parameters = {p.name: p for p in metadata.inputs}
                output_parameters = {p.name: p for p in metadata.outputs}
                for i in node.data.inputs:
                    if i.name in input_parameters:
                        new_param = input_parameters[i.name]
                        i.label = new_param.label
                        i.description = new_param.description
                for i in node.data.outputs:
                    if i.name in output_parameters:
                        new_param = output_parameters[i.name]
                        i.label = new_param.label
                        i.description = new_param.description
            else:
                data = cast(ResourceMetadata, node.data)
                key = data.get_origin_id()
                metadata = _get_resource_class(key).metadata

            for param in metadata.parameters:
                parameters_map[param.name] = param

            # Update the latest metadata.
            node.data.label = metadata.label
            node.data.description = metadata.description
            node.data.category = metadata.category
            node.data.tags = metadata.tags
            node.data.icon = metadata.icon
            node.data.documentation_url = metadata.documentation_url

            for param in node.data.parameters:
                if param.name in parameters_map:
                    new_param = parameters_map[param.name]
                    param.label = new_param.label
                    param.description = new_param.description
                    param.options = new_param.get_dict_options()  # type: ignore
                    param.default = new_param.default
                    param.placeholder = new_param.placeholder

        except (FlowException, ValueError) as e:
            logger.warning(f"Unable to fill the flow panel: {e}")
