"""The mixin of DAGs."""
import abc
import dataclasses
import inspect
from abc import ABC
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar, Union, cast

from dbgpt._private.pydantic import BaseModel, Field, ValidationError, root_validator
from dbgpt.core.awel.util.parameter_util import BaseDynamicOptions, OptionValue
from dbgpt.core.interface.serialization import Serializable

from .exceptions import FlowMetadataException, FlowParameterMetadataException

_TYPE_REGISTRY: Dict[str, Type] = {}


_ALLOWED_TYPES: Dict[str, Type] = {
    "str": str,
    "int": int,
}

_BASIC_TYPES = [str, int, float, bool, dict, list, set]

T = TypeVar("T", bound="ViewMixin")
TM = TypeVar("TM", bound="TypeMetadata")


def _get_type_name(type_: Type[Any]) -> str:
    """Get the type name of the type.

    Register the type if the type is not registered.

    Args:
        type_ (Type[Any]): The type.

    Returns:
        str: The type na
    """
    type_name = f"{type_.__module__}.{type_.__qualname__}"

    if type_name not in _TYPE_REGISTRY:
        _TYPE_REGISTRY[type_name] = type_

    return type_name


def _get_type_cls(type_name: str) -> Type[Any]:
    """Get the type class by the type name.

    Args:
        type_name (str): The type name.

    Returns:
        Type[Any]: The type class.

    Raises:
        ValueError: If the type is not registered.
    """
    if type_name not in _TYPE_REGISTRY:
        raise ValueError(f"Type {type_name} not registered.")
    return _TYPE_REGISTRY[type_name]


# Register the basic types.
for t in _BASIC_TYPES:
    _get_type_name(t)


class _MISSING_TYPE:
    pass


_MISSING_VALUE = _MISSING_TYPE()


def _serialize_complex_obj(obj: Any) -> Any:
    if isinstance(obj, Serializable):
        return obj.to_dict()
    elif dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    else:
        return obj


def _serialize_recursive(data: Any) -> Any:
    if isinstance(data, dict):
        return {key: _serialize_complex_obj(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_serialize_complex_obj(item) for item in data]
    else:
        return _serialize_complex_obj(data)


class _CategoryDetail:
    """The detail of the category."""

    def __init__(self, label: str, description: str):
        """Init the category detail."""
        self.label = label
        self.description = description


_OPERATOR_CATEGORY_DETAIL = {
    "trigger": _CategoryDetail("Trigger", "Trigger your AWEL flow"),
    "llm": _CategoryDetail("LLM", "Invoke LLM model"),
    "conversion": _CategoryDetail("Conversion", "Handle the conversion"),
    "output_parser": _CategoryDetail("Output Parser", "Parse the output of LLM model"),
    "common": _CategoryDetail("Common", "The common operator"),
    "agent": _CategoryDetail("Agent", "The agent operator"),
    "rag": _CategoryDetail("RAG", "The RAG operator"),
}


class OperatorCategory(str, Enum):
    """The category of the operator."""

    TRIGGER = "trigger"
    LLM = "llm"
    CONVERSION = "conversion"
    OUTPUT_PARSER = "output_parser"
    COMMON = "common"
    AGENT = "agent"
    RAG = "rag"

    def label(self) -> str:
        """Get the label of the category."""
        return _OPERATOR_CATEGORY_DETAIL[self.value].label

    def description(self) -> str:
        """Get the description of the category."""
        return _OPERATOR_CATEGORY_DETAIL[self.value].description

    @classmethod
    def value_of(cls, value: str) -> "OperatorCategory":
        """Get the category by the value."""
        for category in cls:
            if category.value == value:
                return category
        raise ValueError(f"Can't find the category for value {value}")


class OperatorType(str, Enum):
    """The type of the operator."""

    MAP = "map"
    REDUCE = "reduce"
    JOIN = "join"
    BRANCH = "branch"
    INPUT = "input"
    STREAMIFY = "streamify"
    UN_STREAMIFY = "un_streamify"
    TRANSFORM_STREAM = "transform_stream"


_RESOURCE_CATEGORY_DETAIL = {
    "http_body": _CategoryDetail("HTTP Body", "The HTTP body"),
    "llm_client": _CategoryDetail("LLM Client", "The LLM client"),
    "storage": _CategoryDetail("Storage", "The storage resource"),
    "serializer": _CategoryDetail("Serializer", "The serializer resource"),
    "common": _CategoryDetail("Common", "The common resource"),
    "prompt": _CategoryDetail("Prompt", "The prompt resource"),
    "agent": _CategoryDetail("Agent", "The agent resource"),
    "rag": _CategoryDetail("RAG", "The  resource"),
}


class ResourceCategory(str, Enum):
    """The category of the resource."""

    HTTP_BODY = "http_body"
    LLM_CLIENT = "llm_client"
    STORAGE = "storage"
    SERIALIZER = "serializer"
    COMMON = "common"
    PROMPT = "prompt"
    AGENT = "agent"
    RAG = "rag"

    def label(self) -> str:
        """Get the label of the category."""
        return _RESOURCE_CATEGORY_DETAIL[self.value].label

    def description(self) -> str:
        """Get the description of the category."""
        return _RESOURCE_CATEGORY_DETAIL[self.value].description

    @classmethod
    def value_of(cls, value: str) -> "ResourceCategory":
        """Get the category by the value."""
        for category in cls:
            if category.value == value:
                return category
        raise ValueError(f"Can't find the category for value {value}")


class ResourceType(str, Enum):
    """The type of the resource."""

    INSTANCE = "instance"
    CLASS = "class"


class ParameterType(str, Enum):
    """The type of the parameter."""

    STRING = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DICT = "dict"
    LIST = "list"


class ParameterCategory(str, Enum):
    """The category of the parameter."""

    COMMON = "common"
    RESOURCER = "resource"

    @classmethod
    def values(cls) -> List[str]:
        """Get the values of the category."""
        return [category.value for category in cls]

    @classmethod
    def get_category(cls, value: Type[Any]) -> "ParameterCategory":
        """Get the category of the value.

        Args:
            value (Any): The value.

        Returns:
            ParameterCategory: The category of the value.
        """
        if value in _BASIC_TYPES:
            return cls.COMMON
        else:
            return cls.RESOURCER


DefaultParameterType = Union[str, int, float, bool, None]


class TypeMetadata(BaseModel):
    """The metadata of the type."""

    type_name: str = Field(
        ..., description="The type short name of the parameter", examples=["str", "int"]
    )

    type_cls: str = Field(
        ...,
        description="The type class of the parameter",
        examples=["builtins.str", "builtins.int"],
    )

    def new(self: TM) -> TM:
        """Copy the metadata."""
        return self.__class__(**self.dict())


class Parameter(TypeMetadata, Serializable):
    """Parameter for build operator."""

    label: str = Field(
        ..., description="The label to display in UI", examples=["OpenAI API Key"]
    )
    name: str = Field(
        ..., description="The name of the parameter", examples=["apk_key"]
    )
    is_list: bool = Field(
        default=False,
        description="Whether current parameter is list",
        examples=[True, False],
    )
    category: str = Field(
        ...,
        description="The category of the parameter",
        examples=["common", "resource"],
    )
    # resource_category: Optional[str] = Field(
    #     default=None,
    #     description="The category of the resource, just for resource type",
    #     examples=["llm_client", "common"],
    # )
    resource_type: ResourceType = Field(
        default=ResourceType.INSTANCE,
        description="The type of the resource, just for resource type",
        examples=["instance", "class"],
    )
    optional: bool = Field(
        ..., description="Whether the parameter is optional", examples=[True, False]
    )
    default: Optional[DefaultParameterType] = Field(
        None, description="The default value of the parameter"
    )
    placeholder: Optional[DefaultParameterType] = Field(
        None, description="The placeholder of the parameter"
    )
    description: Optional[str] = Field(
        None, description="The description of the parameter"
    )
    options: Optional[Union[BaseDynamicOptions, List[OptionValue]]] = Field(
        None, description="The options of the parameter"
    )
    value: Optional[Any] = Field(
        None, description="The value of the parameter(Saved in the dag file)"
    )

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata.

        Transform the value to the real type.
        """
        type_cls = values.get("type_cls")
        to_handle_values = {
            "value": values.get("value"),
            "default": values.get("default"),
        }
        if type_cls:
            for k, v in to_handle_values.items():
                if v:
                    handled_v = cls._covert_to_real_type(type_cls, v)
                    values[k] = handled_v
        return values

    @classmethod
    def _covert_to_real_type(cls, type_cls: str, v: Any):
        if type_cls and v is not None:
            try:
                # Try to convert the value to the type.
                if type_cls == "builtins.str":
                    return str(v)
                elif type_cls == "builtins.int":
                    return int(v)
                elif type_cls == "builtins.float":
                    return float(v)
                elif type_cls == "builtins.bool":
                    if str(v).lower() in ["false", "0", "", "no", "off"]:
                        return False
                    return bool(v)
            except ValueError:
                raise ValidationError(f"Value '{v}' is not valid for type {type_cls}")
        return v

    def get_typed_value(self) -> Any:
        """Get the typed value."""
        return self._covert_to_real_type(self.type_cls, self.value)

    def get_typed_default(self) -> Any:
        """Get the typed default."""
        return self._covert_to_real_type(self.type_cls, self.default)

    @classmethod
    def build_from(
        cls,
        label: str,
        name: str,
        type: Type,
        optional: bool = False,
        default: Optional[Union[DefaultParameterType, _MISSING_TYPE]] = _MISSING_VALUE,
        placeholder: Optional[DefaultParameterType] = None,
        description: Optional[str] = None,
        options: Optional[Union[BaseDynamicOptions, List[OptionValue]]] = None,
        resource_type: ResourceType = ResourceType.INSTANCE,
    ):
        """Build the parameter from the type."""
        type_name = type.__qualname__
        type_cls = _get_type_name(type)
        category = ParameterCategory.get_category(type)
        if optional and default == _MISSING_VALUE:
            raise ValueError(f"Default value is missing for optional parameter {name}.")
        if not optional:
            default = None
        return cls(
            label=label,
            name=name,
            type_name=type_name,
            type_cls=type_cls,
            category=category.value,
            resource_type=resource_type,
            optional=optional,
            default=default,
            placeholder=placeholder,
            description=description or label,
            options=options,
        )

    @classmethod
    def build_from_ui(cls, data: Dict) -> "Parameter":
        """Build the parameter from the type.

        Some fields are not trusted, so we need to check the type.

        Args:
            data (Dict): The parameter data.

        Returns:
            Parameter: The parameter.
        """
        type_str = data["type_cls"]
        type_name = data["type_name"]
        # Build and check the type.
        category = ParameterCategory.get_category(_get_type_cls(type_str))
        return cls(
            label=data["label"],
            name=data["name"],
            type_name=type_name,
            type_cls=type_str,
            category=category.value,
            optional=data["optional"],
            default=data["default"],
            description=data["description"],
            options=data["options"],
            value=data["value"],
        )

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        dict_value = self.dict(exclude={"options"})
        if not self.options:
            dict_value["options"] = None
        elif isinstance(self.options, BaseDynamicOptions):
            values = self.options.option_values()
            dict_value["options"] = [value.to_dict() for value in values]
        else:
            dict_value["options"] = [value.to_dict() for value in self.options]
        return dict_value

    def to_runnable_parameter(
        self,
        view_value: Any,
        resources: Optional[Dict[str, "ResourceMetadata"]] = None,
        key_to_resource_instance: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Convert the parameter to runnable parameter.

        Args:
            view_value (Any): The value from UI.
            resources (Optional[Dict[str, "ResourceMetadata"]], optional):
                The resources. Defaults to None.
            key_to_resource_instance (Optional[Dict[str, Any]], optional):

        Returns:
            Dict: The runnable parameter.
        """
        if (
            view_value is not None
            and self.category == ParameterCategory.RESOURCER
            and resources
            and key_to_resource_instance
        ):
            # Resource type can have multiple parameters.
            resource_id = view_value
            resource_metadata = resources[resource_id]
            # Check the type.
            resource_type = _get_type_cls(resource_metadata.type_cls)
            if self.resource_type == ResourceType.CLASS:
                # Just require the type, not an instance.
                value: Any = resource_type
            else:
                if resource_id not in key_to_resource_instance:
                    raise FlowParameterMetadataException(
                        f"The dependency resource {resource_id} not found."
                    )
                resource_inst = key_to_resource_instance[resource_id]
                value = resource_inst
                if value is not None and not isinstance(value, resource_type):
                    raise FlowParameterMetadataException(
                        f"Resource {resource_id} is not an instance of {resource_type}"
                    )
        else:
            value = self.get_typed_default()
            if self.value is not None:
                value = self.value
            if view_value is not None:
                value = view_value
        return {self.name: value}


class BaseResource(Serializable, BaseModel):
    """The base resource."""

    label: str = Field(
        ...,
        description="The label to display in UI",
        examples=["LLM Operator", "OpenAI LLM Client"],
    )
    name: str = Field(
        ...,
        description="The name of the operator",
        examples=["llm_operator", "openai_llm_client"],
    )
    description: str = Field(
        ...,
        description="The description of the field",
        examples=["The LLM operator.", "OpenAI LLM Client"],
    )

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        return self.dict()


class Resource(BaseResource, TypeMetadata):
    """The resource of the operator."""

    pass


class IOFiledType(str, Enum):
    """The type of the input or output field."""

    STRING = "str"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DICT = "dict"
    LIST = "list"


class IOField(Resource):
    """The input or output field of the operator."""

    is_list: bool = Field(
        default=False,
        description="Whether current field is list",
        examples=[True, False],
    )

    @classmethod
    def build_from(
        cls,
        label: str,
        name: str,
        type: Type,
        description: Optional[str] = None,
        is_list: bool = False,
    ):
        """Build the resource from the type."""
        type_name = type.__qualname__
        type_cls = _get_type_name(type)
        return cls(
            label=label,
            name=name,
            type_name=type_name,
            type_cls=type_cls,
            is_list=is_list,
            description=description or label,
        )


class BaseMetadata(BaseResource):
    """The base metadata."""

    category: Union[OperatorCategory, ResourceCategory] = Field(
        ...,
        description="The category of the operator",
        examples=[OperatorCategory.LLM.value, ResourceCategory.LLM_CLIENT.value],
    )
    category_label: str = Field(
        ...,
        description="The category label of the metadata(Just for UI)",
        examples=["LLM", "Resource"],
    )

    flow_type: Optional[str] = Field(
        ..., description="The flow type", examples=["operator", "resource"]
    )
    icon: Optional[str] = Field(
        default=None,
        description="The icon of the operator or resource",
        examples=["public/awel/icons/llm.svg"],
    )
    documentation_url: Optional[str] = Field(
        default=None,
        description="The documentation url of the operator or resource",
        examples=["https://docs.dbgpt.site/docs/awel"],
    )

    id: str = Field(
        description="The id of the operator or resource",
        examples=[
            "operator_llm_operator___$$___llm___$$___v1",
            "resource_dbgpt.model.proxy.llms.chatgpt.OpenAILLMClient",
        ],
    )

    tags: Optional[List[str]] = Field(
        default=None,
        description="The tags of the operator",
        examples=[["llm", "openai", "gpt3"]],
    )

    parameters: List[Parameter] = Field(
        ..., description="The parameters of the operator or resource"
    )

    @property
    def is_operator(self) -> bool:
        """Whether the metadata is for operator."""
        return self.flow_type == "operator"

    def get_runnable_parameters(
        self,
        view_parameters: Optional[List[Parameter]],
        resources: Optional[Dict[str, "ResourceMetadata"]] = None,
        key_to_resource_instance: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Get the runnable parameters.

        Args:
            view_parameters (Optional[List[Parameter]]):
                The parameters from UI.
            resources (Optional[Dict[str, "ResourceMetadata"]], optional):
                The resources. Defaults to None.
            key_to_resource_instance (Optional[Dict[str, Any]], optional):

        Returns:
            Dict: The runnable parameters.
        """
        runnable_parameters: Dict[str, Any] = {}
        if not self.parameters or not view_parameters:
            return runnable_parameters
        view_required_parameters = {
            parameter.name: parameter
            for parameter in view_parameters
            if not parameter.optional
        }
        current_required_parameters = {
            parameter.name: parameter
            for parameter in self.parameters
            if not parameter.optional
        }
        current_parameters = {
            parameter.name: parameter for parameter in self.parameters
        }
        if len(view_required_parameters) < len(current_required_parameters):
            # TODO, skip the optional parameters.
            raise FlowParameterMetadataException(
                f"Parameters count not match(current key: {self.id}). "
                f"Expected {len(current_required_parameters)}, "
                f"but got {len(view_required_parameters)} from JSON metadata."
                f"Required parameters: {current_required_parameters.keys()}, "
                f"but got {view_required_parameters.keys()}."
            )
        for view_param in view_parameters:
            view_param_key = view_param.name
            if view_param_key not in current_parameters:
                raise FlowParameterMetadataException(
                    f"Parameter {view_param_key} not in the metadata."
                )
            runnable_parameters.update(
                current_parameters[view_param_key].to_runnable_parameter(
                    view_param.get_typed_value(), resources, key_to_resource_instance
                )
            )
        return runnable_parameters

    @root_validator(pre=True)
    def base_pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if "category_label" not in values:
            category = values["category"]
            if isinstance(category, str):
                if issubclass(cls, ResourceMetadata):
                    category = ResourceCategory.value_of(category)
                else:
                    category = OperatorCategory.value_of(category)
            values["category_label"] = category.label()
        return values

    def get_origin_id(self) -> str:
        """Get the origin id."""
        split_ids = self.id.split("_")
        return "_".join(split_ids[:-1])

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        dict_value = self.dict(exclude={"parameters"})
        dict_value["parameters"] = [
            parameter.to_dict() for parameter in self.parameters
        ]
        return dict_value


class ResourceMetadata(BaseMetadata, TypeMetadata):
    """The metadata of the resource."""

    resource_type: ResourceType = Field(
        default=ResourceType.INSTANCE,
        description="The type of the resource",
        examples=["instance", "class"],
    )

    parent_cls: List[str] = Field(
        default_factory=list,
        description="The parent class of the resource",
        examples=[
            "dbgpt.core.interface.llm.LLMClient",
            "resource_dbgpt.model.proxy.llms.chatgpt.OpenAILLMClient",
        ],
    )

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if "flow_type" not in values:
            values["flow_type"] = "resource"
        if "id" not in values:
            values["id"] = values["flow_type"] + "_" + values["type_cls"]
        return values


def register_resource(
    label: str,
    name: Optional[str] = None,
    category: ResourceCategory = ResourceCategory.COMMON,
    parameters: Optional[List[Parameter]] = None,
    description: Optional[str] = None,
    resource_type: ResourceType = ResourceType.INSTANCE,
    **kwargs,
):
    """Register the resource.

    Args:
        label (str): The label of the resource.
        name (Optional[str], optional): The name of the resource. Defaults to None.
        category (str, optional): The category of the resource. Defaults to "common".
        parameters (Optional[List[Parameter]], optional): The parameters of the
            resource. Defaults to None.
        description (Optional[str], optional): The description of the resource.
            Defaults to None.
        resource_type (ResourceType, optional): The type of the resource.
    """
    if resource_type == ResourceType.CLASS and parameters:
        raise ValueError("Class resource can't have parameters.")

    def decorator(cls):
        """Wrap the class."""
        resource_description = description or cls.__doc__
        # Register the type
        type_name = cls.__qualname__
        type_cls = _get_type_name(cls)
        mro = inspect.getmro(cls)
        parent_cls = [
            _get_type_name(parent_cls)
            for parent_cls in mro
            if parent_cls != object and parent_cls != abc.ABC
        ]

        resource_metadata = ResourceMetadata(
            label=label,
            name=name or type_name,
            category=category,
            description=resource_description or label,
            type_name=type_name,
            type_cls=type_cls,
            parameters=parameters or [],
            parent_cls=parent_cls,
            resource_type=resource_type,
            **kwargs,
        )
        _register_resource(cls, resource_metadata)

        # Attach the metadata to the class
        cls._resource_metadata = resource_metadata
        return cls

    return decorator


class ViewMetadata(BaseMetadata):
    """The metadata of the operator.

    We use this metadata to build the operator in UI and view the operator in UI.
    """

    operator_type: OperatorType = Field(
        default=OperatorType.MAP,
        description="The type of the operator",
        examples=["map", "reduce"],
    )
    inputs: List[IOField] = Field(..., description="The inputs of the operator")
    outputs: List[IOField] = Field(..., description="The outputs of the operator")
    version: str = Field(
        default="v1", description="The version of the operator", examples=["v1", "v2"]
    )

    type_name: Optional[str] = Field(
        default=None,
        description="The type short name of the operator",
        examples=["LLMOperator"],
    )

    type_cls: Optional[str] = Field(
        default=None,
        description="The type class of the operator",
        examples=["dbgpt.model.operators.LLMOperator"],
    )

    @root_validator(pre=True)
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if "flow_type" not in values:
            values["flow_type"] = "operator"
        if "id" not in values:
            key = cls.get_key(
                values["name"], values["category"], values.get("version", "v1")
            )
            values["id"] = values["flow_type"] + "_" + key
        inputs = values.get("inputs")
        outputs = values.get("outputs")
        if inputs:
            new_inputs = []
            for field in inputs:
                if isinstance(field, dict):
                    new_inputs.append(IOField(**field))
                elif isinstance(field, IOField):
                    new_inputs.append(field)
                else:
                    raise ValueError("Inputs should be IOField.")

            values["inputs"] = new_inputs
        if outputs:
            new_outputs = []
            for field in outputs:
                if isinstance(field, dict):
                    new_outputs.append(IOField(**field))
                elif isinstance(field, IOField):
                    new_outputs.append(field)
                else:
                    raise ValueError("Outputs should be IOField.")
            values["outputs"] = new_outputs
        return values

    def get_operator_key(self) -> str:
        """Get the operator key."""
        if not self.flow_type:
            raise ValueError("Flow type can't be empty")

        return (
            self.flow_type + "_" + self.get_key(self.name, self.category, self.version)
        )

    @staticmethod
    def get_key(
        name: str,
        category: Union[str, ResourceCategory, OperatorCategory],
        version: str,
    ) -> str:
        """Get the operator id."""
        split_str = "___$$___"
        if isinstance(category, (ResourceCategory, OperatorCategory)):
            category = category.value
        return f"{name}{split_str}{category}{split_str}{version}"


class ViewMixin(ABC):
    """The mixin of the operator."""

    metadata: Optional[ViewMetadata] = None

    def get_view_metadata(self) -> Optional[ViewMetadata]:
        """Get the view metadata.

        Returns:
            Optional[ViewMetadata]: The view metadata.
        """
        return self.metadata

    @classmethod
    def after_define(cls):
        """After define the operator, register the operator."""
        _register_operator(cls)

    def to_dict(self) -> Dict:
        """Convert current metadata to json.

        Show the metadata in UI.

        Returns:
            Dict: The metadata dict.

        Raises:
            ValueError: If the metadata is not set.
        """
        metadata = self.get_view_metadata()
        if not metadata:
            raise ValueError("Metadata is not set.")
        metadata_dict = metadata.to_dict()
        return metadata_dict

    @classmethod
    def build_from(
        cls: Type[T],
        view_metadata: ViewMetadata,
        key_to_resource: Optional[Dict[str, "ResourceMetadata"]] = None,
    ) -> T:
        """Build the operator from the metadata."""
        operator_key = view_metadata.get_operator_key()
        operator_cls: Type[T] = _get_operator_class(operator_key)
        metadata = operator_cls.metadata
        if not metadata:
            raise ValueError("Metadata is not set.")
        runnable_params = metadata.get_runnable_parameters(
            view_metadata.parameters, key_to_resource
        )
        operator_task: T = operator_cls(**runnable_params)
        return operator_task


@dataclasses.dataclass
class _RegistryItem:
    """The registry item."""

    key: str
    cls: Type
    metadata: Union[ViewMetadata, ResourceMetadata]


class FlowRegistry:
    """The registry of the operator and resource."""

    def __init__(self):
        """Init the registry."""
        self._registry: Dict[str, _RegistryItem] = {}

    def register_flow(
        self, view_cls: Type, metadata: Union[ViewMetadata, ResourceMetadata]
    ):
        """Register the operator."""
        key = metadata.id
        self._registry[key] = _RegistryItem(key=key, cls=view_cls, metadata=metadata)

    def get_registry_item(self, key: str) -> Optional[_RegistryItem]:
        """Get the registry item by the key."""
        return self._registry.get(key)

    def metadata_list(self):
        """Get the metadata list."""
        return [item.metadata.to_dict() for item in self._registry.values()]


_OPERATOR_REGISTRY: FlowRegistry = FlowRegistry()


def _get_operator_class(type_key: str) -> Type[T]:
    """Get the operator class by the type name."""
    item = _OPERATOR_REGISTRY.get_registry_item(type_key)
    if not item:
        raise FlowMetadataException(f"Operator {type_key} not registered.")
    cls = item.cls
    if not issubclass(cls, ViewMixin):
        raise ValueError(f"Operator {type_key} is not a ViewMixin.")
    return cast(Type[T], cls)


def _register_operator(view_cls: Optional[Type[T]]):
    """Register the operator."""
    if not view_cls or not view_cls.metadata:
        return
    metadata = view_cls.metadata
    metadata.type_name = view_cls.__qualname__
    metadata.type_cls = _get_type_name(view_cls)
    _OPERATOR_REGISTRY.register_flow(view_cls, metadata)


def _get_resource_class(type_key: str) -> _RegistryItem:
    """Get the operator class by the type name."""
    item = _OPERATOR_REGISTRY.get_registry_item(type_key)
    if not item:
        raise FlowMetadataException(f"Resource {type_key} not registered.")
    if not isinstance(item.metadata, ResourceMetadata):
        raise ValueError(f"Resource {type_key} is not a ResourceMetadata.")
    return item


def _register_resource(cls: Type, resource_metadata: ResourceMetadata):
    """Register the operator."""
    _OPERATOR_REGISTRY.register_flow(cls, resource_metadata)
