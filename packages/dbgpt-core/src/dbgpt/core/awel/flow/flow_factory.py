"""Build AWEL DAGs from serialized data."""

import dataclasses
import logging
import uuid
from contextlib import suppress
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional, Type, Union, cast

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
from dbgpt.configs import VARIABLES_SCOPE_FLOW_PRIVATE
from dbgpt.core.awel.dag.base import DAG, DAGNode
from dbgpt.core.awel.dag.dag_manager import DAGMetadata

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        dict_value = model_to_dict(self, exclude={"data"})
        dict_value["data"] = self.data.to_dict()
        return dict_value


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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        dict_value = model_to_dict(self, exclude={"nodes"})
        dict_value["nodes"] = [n.to_dict() for n in self.nodes]
        return dict_value


class _VariablesRequestBase(BaseModel):
    key: str = Field(
        ...,
        description="The key of the variable to create",
        examples=["dbgpt.model.openai.api_key"],
    )

    label: str = Field(
        ...,
        description="The label of the variable to create",
        examples=["My First OpenAI Key"],
    )

    description: Optional[str] = Field(
        None,
        description="The description of the variable to create",
        examples=["Your OpenAI API key"],
    )
    value_type: Literal["str", "int", "float", "bool"] = Field(
        "str",
        description="The type of the value of the variable to create",
        examples=["str", "int", "float", "bool"],
    )
    category: Literal["common", "secret"] = Field(
        ...,
        description="The category of the variable to create",
        examples=["common"],
    )
    scope: str = Field(
        ...,
        description="The scope of the variable to create",
        examples=["global"],
    )
    scope_key: Optional[str] = Field(
        None,
        description="The scope key of the variable to create",
        examples=["dbgpt"],
    )


class VariablesRequest(_VariablesRequestBase):
    """Variable request model.

    For creating a new variable in the DB-GPT.
    """

    name: str = Field(
        ...,
        description="The name of the variable to create",
        examples=["my_first_openai_key"],
    )
    value: Any = Field(
        ..., description="The value of the variable to create", examples=["1234567890"]
    )
    enabled: Optional[bool] = Field(
        True,
        description="Whether the variable is enabled",
        examples=[True],
    )
    user_name: Optional[str] = Field(None, description="User name")
    sys_code: Optional[str] = Field(None, description="System code")


class ParsedFlowVariables(BaseModel):
    """Parsed variables for the flow."""

    key: str = Field(
        ...,
        description="The key of the variable",
        examples=["dbgpt.model.openai.api_key"],
    )
    name: Optional[str] = Field(
        None,
        description="The name of the variable",
        examples=["my_first_openai_key"],
    )
    scope: str = Field(
        ...,
        description="The scope of the variable",
        examples=["global"],
    )
    scope_key: Optional[str] = Field(
        None,
        description="The scope key of the variable",
        examples=["dbgpt"],
    )
    sys_code: Optional[str] = Field(None, description="System code")
    user_name: Optional[str] = Field(None, description="User name")


class FlowVariables(_VariablesRequestBase):
    """Variables for the flow."""

    name: Optional[str] = Field(
        None,
        description="The name of the variable",
        examples=["my_first_openai_key"],
    )
    value: Optional[Any] = Field(
        None, description="The value of the variable", examples=["1234567890"]
    )
    parsed_variables: Optional[ParsedFlowVariables] = Field(
        None, description="The parsed variables, parsed from the value"
    )

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if not isinstance(values, dict):
            return values
        if "parsed_variables" not in values:
            parsed_variables = cls.parse_value_to_variables(values.get("value"))
            if parsed_variables:
                values["parsed_variables"] = parsed_variables
        return values

    @classmethod
    def parse_value_to_variables(cls, value: Any) -> Optional[ParsedFlowVariables]:
        """Parse the value to variables.

        Args:
            value (Any): The value to parse

        Returns:
            Optional[ParsedFlowVariables]: The parsed variables, None if the value is
                invalid
        """
        from ...interface.variables import _is_variable_format, parse_variable

        if not value or not isinstance(value, str) or not _is_variable_format(value):
            return None

        variable_dict = parse_variable(value)
        return ParsedFlowVariables(**variable_dict)


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
    metadata: Optional[Union[DAGMetadata, Dict[str, Any]]] = Field(
        default=None, description="The metadata of the flow"
    )
    variables: Optional[List[FlowVariables]] = Field(
        default=None, description="The variables of the flow"
    )
    authors: Optional[List[str]] = Field(
        default=None, description="The authors of the flow"
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

    def model_dump(self, **kwargs):
        """Override the model dump method."""
        exclude = kwargs.get("exclude", set())
        if "flow_dag" not in exclude:
            exclude.add("flow_dag")
        if "flow_data" not in exclude:
            exclude.add("flow_data")
        kwargs["exclude"] = exclude
        common_dict = super().model_dump(**kwargs)
        if self.flow_dag:
            common_dict["flow_dag"] = None
        if self.flow_data:
            common_dict["flow_data"] = self.flow_data.to_dict()
        return common_dict

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return model_to_dict(self, exclude={"flow_dag", "flow_data"})

    def get_variables_dict(self) -> List[Dict[str, Any]]:
        """Get the variables dict."""
        if not self.variables:
            return []
        return [v.dict() for v in self.variables]

    @classmethod
    def parse_variables(
        cls, variables: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[List[FlowVariables]]:
        """Parse the variables."""
        if not variables:
            return None
        return [FlowVariables(**v) for v in variables]


@dataclasses.dataclass
class _KeyToNodeItem:
    """Key to node item."""

    key: str
    source_order: int
    target_order: int
    mappers: List[str]
    edge_index: int


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
        # Record current node's downstream
        key_to_downstream: Dict[str, List[_KeyToNodeItem]] = {}
        # Record current node's upstream
        key_to_upstream: Dict[str, List[_KeyToNodeItem]] = {}
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

        if not key_to_operator_nodes and not key_to_resource_nodes:
            raise FlowMetadataException(
                "No operator or resource nodes found in the flow."
            )

        for edge_index, edge in enumerate(flow_data.edges):
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
                mappers = []
                for i, out in enumerate(source_node.data.outputs):
                    if i != edge.source_order:
                        continue
                    if out.mappers:
                        # Current edge is a mapper edge, find the mappers.
                        mappers = out.mappers
                # Note: Not support mappers in the inputs of the target node now.

                downstream = key_to_downstream.get(source_key, [])
                downstream.append(
                    _KeyToNodeItem(
                        key=target_key,
                        source_order=edge.source_order,
                        target_order=edge.target_order,
                        mappers=mappers,
                        edge_index=edge_index,
                    )
                )
                key_to_downstream[source_key] = downstream

                upstream = key_to_upstream.get(target_key, [])
                upstream.append(
                    _KeyToNodeItem(
                        key=source_key,
                        source_order=edge.source_order,
                        target_order=edge.target_order,
                        mappers=mappers,
                        edge_index=edge_index,
                    )
                )
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
            key_to_downstream[key] = sorted(value, key=lambda x: x.source_order)
        for key, value in key_to_upstream.items():
            # Sort by target_order.
            key_to_upstream[key] = sorted(value, key=lambda x: x.target_order)

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
                logger.warning(str(e), e)
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
        key_to_downstream: Dict[str, List[_KeyToNodeItem]],
        key_to_upstream: Dict[str, List[_KeyToNodeItem]],
        dag_id: Optional[str] = None,
    ) -> DAG:
        """Build the DAG."""
        from ..dag.base import DAGVariables, _DAGVariablesItem

        formatted_name = flow_panel.name.replace(" ", "_")
        if not dag_id:
            dag_id = f"{self._dag_prefix}_{formatted_name}_{flow_panel.uid}"

        default_dag_variables: Optional[DAGVariables] = None
        if flow_panel.variables:
            variables = []
            for v in flow_panel.variables:
                scope_key = v.scope_key
                if v.scope == VARIABLES_SCOPE_FLOW_PRIVATE and not scope_key:
                    scope_key = dag_id
                variables.append(
                    _DAGVariablesItem(
                        key=v.key,
                        name=v.name,  # type: ignore
                        label=v.label,
                        description=v.description,
                        value_type=v.value_type,
                        category=v.category,
                        scope=v.scope,
                        scope_key=scope_key,
                        value=v.value,
                        user_name=flow_panel.user_name,
                        sys_code=flow_panel.sys_code,
                    )
                )
            default_dag_variables = DAGVariables(items=variables)
        with DAG(dag_id, default_dag_variables=default_dag_variables) as dag:
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
                for up_item in upstream:
                    upstream_key = up_item.key
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
                    tasks = _build_mapper_operators(dag, up_item.mappers)
                    tasks.append(task)
                    last_task = upstream_task
                    for t in tasks:
                        # Connect the task to the upstream task.
                        last_task >> t
                        last_task = t
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
    key_to_upstream_node: Dict[str, List[FlowNodeData]],
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


def _build_mapper_operators(dag: DAG, mappers: List[str]) -> List[DAGNode]:
    from .base import _get_type_cls

    tasks = []
    for mapper in mappers:
        try:
            mapper_cls = _get_type_cls(mapper)
            task = mapper_cls()
            if not task._node_id:
                task.set_node_id(dag._new_node_id())
            tasks.append(task)
        except Exception as e:
            err_msg = f"Unable to build mapper task: {mapper}, error: {e}"
            raise FlowMetadataException(err_msg)
    return tasks


def fill_flow_panel(
    flow_panel: FlowPanel,
    metadata_func: Callable[
        [Union[ViewMetadata, ResourceMetadata]], Union[ViewMetadata, ResourceMetadata]
    ] = None,
    ignore_options_error: bool = False,
    update_id: bool = False,
):
    """Fill the flow panel with the latest metadata.

    Args:
        flow_panel (FlowPanel): The flow panel to fill.
    """
    if not flow_panel.flow_data:
        return
    id_mapping = {}
    for node in flow_panel.flow_data.nodes:
        try:
            parameters_map = {}
            if node.data.is_operator:
                data = cast(ViewMetadata, node.data)
                metadata = None
                if metadata_func:
                    metadata = metadata_func(data)
                if not metadata:
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
                        i.type_name = new_param.type_name
                        i.type_cls = new_param.type_cls
                        i.label = new_param.label
                        i.description = new_param.description
                        i.dynamic = new_param.dynamic
                        i.is_list = new_param.is_list
                        i.dynamic_minimum = new_param.dynamic_minimum
                        i.mappers = new_param.mappers
                for i in node.data.outputs:
                    if i.name in output_parameters:
                        new_param = output_parameters[i.name]
                        i.type_name = new_param.type_name
                        i.type_cls = new_param.type_cls
                        i.label = new_param.label
                        i.description = new_param.description
                        i.dynamic = new_param.dynamic
                        i.is_list = new_param.is_list
                        i.dynamic_minimum = new_param.dynamic_minimum
                        i.mappers = new_param.mappers
            else:
                data = cast(ResourceMetadata, node.data)
                metadata = None
                if metadata_func:
                    metadata = metadata_func(data)
                if not metadata:
                    key = data.get_origin_id()
                    metadata = _get_resource_class(key).metadata

            for param in metadata.parameters:
                parameters_map[param.name] = param

            # Update the latest metadata.
            if node.data.type_cls != metadata.type_cls:
                old_type_cls = node.data.type_cls
                node.data.type_cls = metadata.type_cls
                node.data.type_name = metadata.type_name
                if not node.data.is_operator and update_id:
                    # Update key
                    old_id = data.id
                    new_id = old_id.replace(old_type_cls, metadata.type_cls)
                    data.id = new_id
                    id_mapping[old_id] = new_id
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
                    try:
                        param.options = new_param.get_dict_options()  # type: ignore
                    except Exception as e:
                        if ignore_options_error:
                            logger.warning(
                                f"Unable to fill the options for the parameter: {e}"
                            )
                        else:
                            raise
                    param.type_cls = new_param.type_cls
                    param.optional = new_param.optional
                    param.default = new_param.default
                    param.placeholder = new_param.placeholder
                    param.alias = new_param.alias
                    param.ui = new_param.ui
                    param.is_list = new_param.is_list
                    param.dynamic = new_param.dynamic
                    param.dynamic_minimum = new_param.dynamic_minimum

        except (FlowException, ValueError) as e:
            logger.warning(f"Unable to fill the flow panel: {e}")

    if not update_id:
        return

    for edge in flow_panel.flow_data.edges:
        for old_id, new_id in id_mapping.items():
            edge.source.replace(old_id, new_id)
            edge.target.replace(old_id, new_id)
            edge.source_handle.replace(old_id, new_id)
            edge.target_handle.replace(old_id, new_id)
