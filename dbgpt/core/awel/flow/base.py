"""The mixin of DAGs."""

import abc
import dataclasses
import inspect
from abc import ABC
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Type, TypeVar, Union, cast

from dbgpt._private.pydantic import (
    BaseModel,
    Field,
    ValidationError,
    model_to_dict,
    model_validator,
)
from dbgpt.component import SystemApp
from dbgpt.core.awel.util.parameter_util import (
    BaseDynamicOptions,
    OptionValue,
    RefreshOptionRequest,
)
from dbgpt.core.interface.serialization import Serializable
from dbgpt.util.executor_utils import DefaultExecutorFactory, blocking_func_to_async

from .exceptions import FlowMetadataException, FlowParameterMetadataException
from .ui import UIComponent

_TYPE_REGISTRY: Dict[str, Type] = {}


_ALLOWED_TYPES: Dict[str, Type] = {
    "str": str,
    "int": int,
}

_BASIC_TYPES = [str, int, float, bool, dict, list, set]
_DYNAMIC_PARAMETER_TYPES = [str, int, float, bool]
DefaultParameterType = Union[str, int, float, bool, None]

T = TypeVar("T", bound="ViewMixin")
TM = TypeVar("TM", bound="TypeMetadata")

TAGS_ORDER_HIGH = "higher-order"
TAGS_ORDER_FIRST = "first-order"


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


def _register_alias_types(type_: Type[Any], alias_ids: Optional[List[str]] = None):
    if alias_ids:
        for alias_id in alias_ids:
            if alias_id not in _TYPE_REGISTRY:
                _TYPE_REGISTRY[alias_id] = type_


def _get_type_cls(type_name: str) -> Type[Any]:
    """Get the type class by the type name.

    Args:
        type_name (str): The type name.

    Returns:
        Type[Any]: The type class.

    Raises:
        ValueError: If the type is not registered.
    """
    from .compat import get_new_class_name

    new_cls = get_new_class_name(type_name)
    if type_name in _TYPE_REGISTRY:
        return _TYPE_REGISTRY[type_name]
    elif new_cls and new_cls in _TYPE_REGISTRY:
        return _TYPE_REGISTRY[new_cls]
    else:
        raise ValueError(f"Type {type_name} not registered.")


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
    "sender": _CategoryDetail("Sender", "Send the data to the target"),
    "llm": _CategoryDetail("LLM", "Invoke LLM model"),
    "conversion": _CategoryDetail("Conversion", "Handle the conversion"),
    "output_parser": _CategoryDetail("Output Parser", "Parse the output of LLM model"),
    "common": _CategoryDetail("Common", "The common operator"),
    "agent": _CategoryDetail("Agent", "The agent operator"),
    "rag": _CategoryDetail("RAG", "The RAG operator"),
    "experimental": _CategoryDetail("EXPERIMENTAL", "EXPERIMENTAL operator"),
    "database": _CategoryDetail("Database", "Interact with the database"),
    "type_converter": _CategoryDetail("Type Converter", "Convert the type"),
    "example": _CategoryDetail("Example", "Example operator"),
    "code": _CategoryDetail("Code", "Code operator"),
}


class OperatorCategory(str, Enum):
    """The category of the operator."""

    TRIGGER = "trigger"
    SENDER = "sender"
    LLM = "llm"
    CONVERSION = "conversion"
    OUTPUT_PARSER = "output_parser"
    COMMON = "common"
    AGENT = "agent"
    RAG = "rag"
    EXPERIMENTAL = "experimental"
    DATABASE = "database"
    TYPE_CONVERTER = "type_converter"
    EXAMPLE = "example"
    CODE = "code"

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
    "embeddings": _CategoryDetail("Embeddings", "The embeddings resource"),
    "rag": _CategoryDetail("RAG", "The  resource"),
    "vector_store": _CategoryDetail("Vector Store", "The vector store resource"),
    "database": _CategoryDetail("Database", "Interact with the database"),
    "example": _CategoryDetail("Example", "The example resource"),
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
    EMBEDDINGS = "embeddings"
    RAG = "rag"
    VECTOR_STORE = "vector_store"
    DATABASE = "database"
    EXAMPLE = "example"

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
        return self.__class__(**self.model_dump(exclude_defaults=True))


class BaseDynamic(BaseModel):
    """The base dynamic field."""

    dynamic: bool = Field(
        default=False,
        description="Whether current field is dynamic",
        examples=[True, False],
    )
    dynamic_minimum: int = Field(
        default=0,
        description="The minimum count of the dynamic field, only valid when dynamic is"
        " True",
        examples=[0, 1, 2],
    )


class Parameter(BaseDynamic, TypeMetadata, Serializable):
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
    alias: Optional[List[str]] = Field(
        None, description="The alias of the parameter(Compatible with old version)"
    )
    ui: Optional[UIComponent] = Field(
        None, description="The UI component of the parameter"
    )

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata.

        Transform the value to the real type.
        """
        if not isinstance(values, dict):
            return values
        type_cls = values.get("type_cls")
        to_handle_values = {
            "value": values.get("value"),
            "default": values.get("default"),
        }
        is_list = values.get("is_list") or False
        if type_cls:
            for k, v in to_handle_values.items():
                if v:
                    handled_v = cls._covert_to_real_type(type_cls, v, is_list)
                    values[k] = handled_v
        return values

    @model_validator(mode="after")
    def check_parameters(self) -> "Parameter":
        """Check the parameters."""
        if self.dynamic and not self.is_list:
            raise FlowMetadataException("Dynamic parameter must be list.")
        if self.dynamic and self.dynamic_minimum < 0:
            raise FlowMetadataException(
                "Dynamic minimum must be greater then or equal to 0."
            )
        return self

    @classmethod
    def _covert_to_real_type(cls, type_cls: str, v: Any, is_list: bool) -> Any:
        def _parse_single_value(vv: Any) -> Any:
            typed_value: Any = vv
            try:
                # Try to convert the value to the type.
                if type_cls == "builtins.str":
                    typed_value = str(vv)
                elif type_cls == "builtins.int":
                    typed_value = int(vv)
                elif type_cls == "builtins.float":
                    typed_value = float(vv)
                elif type_cls == "builtins.bool":
                    if str(vv).lower() in ["false", "0", "", "no", "off"]:
                        return False
                    typed_value = bool(vv)
                return typed_value
            except ValueError:
                raise ValidationError(f"Value '{vv}' is not valid for type {type_cls}")

        if type_cls and v is not None:
            if not is_list:
                _parse_single_value(v)
            else:
                if not isinstance(v, list):
                    raise ValidationError(f"Value '{v}' is not a list.")
                return [_parse_single_value(vv) for vv in v]
        return v

    def get_typed_value(self) -> Any:
        """Get the typed value.

        Returns:
            Any: The typed value. VariablesPlaceHolder if the value is a variable
                string. Otherwise, the real type value.
        """
        from ...interface.variables import VariablesPlaceHolder, is_variable_string

        is_variables = is_variable_string(self.value) if self.value else False
        if is_variables and self.value is not None and isinstance(self.value, str):
            return VariablesPlaceHolder(self.name, self.value)
        else:
            return self._covert_to_real_type(self.type_cls, self.value, self.is_list)

    def get_typed_default(self) -> Any:
        """Get the typed default."""
        return self._covert_to_real_type(self.type_cls, self.default, self.is_list)

    @classmethod
    def build_from(
        cls,
        label: str,
        name: str,
        type: Type,
        is_list: bool = False,
        optional: bool = False,
        default: Optional[Union[DefaultParameterType, _MISSING_TYPE]] = _MISSING_VALUE,
        placeholder: Optional[DefaultParameterType] = None,
        description: Optional[str] = None,
        options: Optional[Union[BaseDynamicOptions, List[OptionValue]]] = None,
        resource_type: ResourceType = ResourceType.INSTANCE,
        dynamic: bool = False,
        dynamic_minimum: int = 0,
        alias: Optional[List[str]] = None,
        ui: Optional[UIComponent] = None,
    ):
        """Build the parameter from the type."""
        type_name = type.__qualname__
        type_cls = _get_type_name(type)
        category = ParameterCategory.get_category(type)
        if optional and default == _MISSING_VALUE:
            raise ValueError(f"Default value is missing for optional parameter {name}.")
        if not optional:
            default = None
        if dynamic and type not in _DYNAMIC_PARAMETER_TYPES:
            raise ValueError("Dynamic parameter must be str, int, float or bool.")
        return cls(
            label=label,
            name=name,
            type_name=type_name,
            type_cls=type_cls,
            is_list=is_list,
            category=category.value,
            resource_type=resource_type,
            optional=optional,
            default=default,
            placeholder=placeholder,
            description=description or label,
            options=options,
            dynamic=dynamic,
            dynamic_minimum=dynamic_minimum,
            alias=alias,
            ui=ui,
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
            ui=data.get("ui"),
        )

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        dict_value = model_to_dict(self, exclude={"options", "alias", "ui"})
        if not self.options:
            dict_value["options"] = None
        elif isinstance(self.options, BaseDynamicOptions):
            values = self.options.option_values()
            dict_value["options"] = [value.to_dict() for value in values]
        else:
            dict_value["options"] = [
                value.to_dict() if not isinstance(value, dict) else value
                for value in self.options
            ]

        if self.ui:
            dict_value["ui"] = self.ui.to_dict()
        return dict_value

    async def refresh(
        self,
        request: Optional[RefreshOptionRequest] = None,
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> Dict:
        """Refresh the options of the parameter.

        Args:
            request (RefreshOptionRequest): The request to refresh the options.
            trigger (Literal["default", "http"], optional): The trigger type.
                Defaults to "default".
            system_app (Optional[SystemApp], optional): The system app.

        Returns:
            Dict: The response.
        """
        dict_value = self.to_dict()
        if not self.options:
            dict_value["options"] = None
        elif isinstance(self.options, BaseDynamicOptions):
            values = self.options.refresh(request, trigger, system_app)
            dict_value["options"] = [value.to_dict() for value in values]
        else:
            dict_value["options"] = [value.to_dict() for value in self.options]
        return dict_value

    def get_dict_options(self) -> Optional[List[Dict]]:
        """Get the options of the parameter."""
        if not self.options:
            return None
        elif isinstance(self.options, BaseDynamicOptions):
            values = self.options.option_values()
            return [value.to_dict() for value in values]
        else:
            return [value.to_dict() for value in self.options]

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
            if resource_id not in resources:
                return {self.name: None}
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

    def new(self: TM) -> TM:
        """Copy the metadata."""
        new_obj = self.__class__(
            **self.model_dump(exclude_defaults=True, exclude={"ui", "options"})
        )
        if self.ui:
            new_obj.ui = self.ui
        if self.options:
            new_obj.options = self.options
        return new_obj


class BaseResource(Serializable, BaseModel):
    """The base resource."""

    label: str = Field(
        ...,
        description="The label to display in UI",
        examples=["LLM Operator", "OpenAI LLM Client"],
    )
    custom_label: Optional[str] = Field(
        None,
        description="The custom label to display in UI",
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
        return model_to_dict(self)


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


class IOField(BaseDynamic, Resource):
    """The input or output field of the operator."""

    is_list: bool = Field(
        default=False,
        description="Whether current field is list",
        examples=[True, False],
    )
    mappers: Optional[List[str]] = Field(
        default=None,
        description="The mappers of the field, transform the field to the target type",
    )

    @classmethod
    def build_from(
        cls,
        label: str,
        name: str,
        type: Type,
        description: Optional[str] = None,
        is_list: bool = False,
        dynamic: bool = False,
        dynamic_minimum: int = 0,
        mappers: Optional[Union[Type, List[Type]]] = None,
    ):
        """Build the resource from the type."""
        type_name = type.__qualname__
        type_cls = _get_type_name(type)
        # TODO: Check the mapper instance can be created without required
        #  parameters.
        if mappers and not isinstance(mappers, list):
            mappers = [mappers]
        mappers_cls = [_get_type_name(m) for m in mappers] if mappers else None
        return cls(
            label=label,
            name=name,
            type_name=type_name,
            type_cls=type_cls,
            is_list=is_list,
            description=description or label,
            dynamic=dynamic,
            dynamic_minimum=dynamic_minimum,
            mappers=mappers_cls,
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

    tags: Optional[Dict[str, str]] = Field(
        default=None,
        description="The tags of the operator",
        examples=[{"order": "higher-order"}, {"order": "first-order"}],
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
        current_parameters = {}
        current_aliases_parameters = {}
        for parameter in self.parameters:
            current_parameters[parameter.name] = parameter
            if parameter.alias:
                for alias in parameter.alias:
                    if alias in current_aliases_parameters:
                        raise FlowMetadataException(
                            f"Alias {alias} already exists in the metadata."
                        )
                    current_aliases_parameters[alias] = parameter

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
            if view_param_key in current_parameters:
                current_parameter = current_parameters[view_param_key]
            elif view_param_key in current_aliases_parameters:
                current_parameter = current_aliases_parameters[view_param_key]
            else:
                raise FlowParameterMetadataException(
                    f"Parameter {view_param_key} not in the metadata."
                )
            runnable_parameters.update(
                current_parameter.to_runnable_parameter(
                    view_param.get_typed_value(), resources, key_to_resource_instance
                )
            )
        return runnable_parameters

    @model_validator(mode="before")
    @classmethod
    def base_pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if not isinstance(values, dict):
            return values
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

    def _parse_ui_size(self) -> Optional[str]:
        """Parse the ui size."""
        if not self.parameters:
            return None
        parameters_size = set()
        for parameter in self.parameters:
            if parameter.ui and parameter.ui.size:
                parameters_size.add(parameter.ui.size)
        for size in ["large", "middle", "small"]:
            if size in parameters_size:
                return size
        return None

    def to_dict(self) -> Dict:
        """Convert current metadata to json dict."""
        from .ui import _size_to_order

        dict_value = model_to_dict(self, exclude={"parameters"})
        tags = dict_value.get("tags")
        if not tags:
            tags = {"ui_version": "flow2.0"}
        elif isinstance(tags, dict) and "ui_version" not in tags:
            tags["ui_version"] = "flow2.0"

        parsed_ui_size = self._parse_ui_size()
        if parsed_ui_size:
            exist_size = tags.get("ui_size")
            if not exist_size or _size_to_order(parsed_ui_size) > _size_to_order(
                exist_size
            ):
                # Use the higher order size as current size.
                tags["ui_size"] = parsed_ui_size

        dict_value["tags"] = tags
        dict_value["parameters"] = [
            parameter.to_dict() for parameter in self.parameters
        ]
        return dict_value

    async def refresh(
        self,
        request: List[RefreshOptionRequest],
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> Dict:
        """Refresh the metadata.

        Args:
            request (List[RefreshOptionRequest]): The refresh request
            trigger (Literal["default", "http"]): The trigger type, how to trigger
                the refresh
            system_app (Optional[SystemApp]): The system app
        """
        executor = DefaultExecutorFactory.get_instance(system_app).create()

        name_to_request = {req.name: req for req in request}
        parameter_requests = {
            parameter.name: name_to_request.get(parameter.name)
            for parameter in self.parameters
        }
        dict_value = model_to_dict(self, exclude={"parameters"})
        parameters = []
        for parameter in self.parameters:
            parameter_dict = parameter.to_dict()
            parameter_request = parameter_requests.get(parameter.name)
            if not parameter.options:
                options = None
            elif isinstance(parameter.options, BaseDynamicOptions):
                options_obj = parameter.options
                if options_obj.support_async(system_app, parameter_request):
                    values = await options_obj.async_refresh(
                        parameter_request, trigger, system_app
                    )
                else:
                    values = await blocking_func_to_async(
                        executor,
                        options_obj.refresh,
                        parameter_request,
                        trigger,
                        system_app,
                    )
                options = [value.to_dict() for value in values]
            else:
                options = [value.to_dict() for value in self.options]
            parameter_dict["options"] = options
            parameters.append(parameter_dict)

        dict_value["parameters"] = parameters

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

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if not isinstance(values, dict):
            return values
        if "flow_type" not in values:
            values["flow_type"] = "resource"
        if "id" not in values:
            values["id"] = values["flow_type"] + "_" + values["type_cls"]
        return values

    def new_alias(self, alias: Optional[List[str]] = None) -> List[str]:
        """Get the new alias id."""
        if not alias:
            return []
        return [f"{self.flow_type}_{a}" for a in alias]


def register_resource(
    label: str,
    name: Optional[str] = None,
    category: ResourceCategory = ResourceCategory.COMMON,
    parameters: Optional[List[Parameter]] = None,
    description: Optional[str] = None,
    resource_type: ResourceType = ResourceType.INSTANCE,
    alias: Optional[List[str]] = None,
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
        alias (Optional[List[str]], optional): The alias of the resource. Defaults to
            None. For compatibility, we can use the alias to register the resource.

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
        alias_ids = resource_metadata.new_alias(alias)
        _register_alias_types(cls, alias_ids)
        _register_resource(cls, resource_metadata, alias_ids)
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

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Pre fill the metadata."""
        if not isinstance(values, dict):
            return values
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

    @model_validator(mode="after")
    def check_metadata(self) -> "ViewMetadata":
        """Check the metadata."""
        if self.inputs:
            for field in self.inputs:
                if field.mappers:
                    raise ValueError("Input field can't have mappers.")
            dyn_cnt, is_last_field_dynamic = 0, False
            for field in self.inputs:
                if field.dynamic:
                    dyn_cnt += 1
                    is_last_field_dynamic = True
                else:
                    if is_last_field_dynamic:
                        raise ValueError("Dynamic field input must be the last field.")
                    is_last_field_dynamic = False
            if dyn_cnt > 1:
                raise ValueError("Only one dynamic input field is allowed.")
        if self.outputs:
            dyn_cnt, is_last_field_dynamic = 0, False
            for field in self.outputs:
                if field.dynamic:
                    dyn_cnt += 1
                    is_last_field_dynamic = True
                else:
                    if is_last_field_dynamic:
                        raise ValueError("Dynamic field output must be the last field.")
                    is_last_field_dynamic = False
            if dyn_cnt > 1:
                raise ValueError("Only one dynamic output field is allowed.")
        return self

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
        self,
        view_cls: Type,
        metadata: Union[ViewMetadata, ResourceMetadata],
        alias_ids: Optional[List[str]] = None,
    ):
        """Register the operator."""
        key = metadata.id
        self._registry[key] = _RegistryItem(key=key, cls=view_cls, metadata=metadata)
        if alias_ids:
            for alias_id in alias_ids:
                self._registry[alias_id] = _RegistryItem(
                    key=alias_id, cls=view_cls, metadata=metadata
                )

    def get_registry_item(self, key: str) -> Optional[_RegistryItem]:
        """Get the registry item by the key."""
        return self._registry.get(key)

    def metadata_list(
        self,
        tags: Optional[Dict[str, str]] = None,
        user_name: Optional[str] = None,
        sys_code: Optional[str] = None,
    ) -> List[Dict]:
        """Get the metadata list.

        TODO: Support the user and system code filter.

        Args:
            tags (Optional[Dict[str, str]], optional): The tags. Defaults to None.
            user_name (Optional[str], optional): The user name. Defaults to None.
            sys_code (Optional[str], optional): The system code. Defaults to None.

        Returns:
            List[Dict]: The metadata list.
        """
        if not tags:
            return [item.metadata.to_dict() for item in self._registry.values()]
        else:
            results = []
            for item in self._registry.values():
                node_tags = item.metadata.tags
                is_match = True
                if not node_tags or not isinstance(node_tags, dict):
                    continue
                for k, v in tags.items():
                    if node_tags.get(k) != v:
                        is_match = False
                        break
                if is_match:
                    results.append(item.metadata.to_dict())
            return results

    async def refresh(
        self,
        key: str,
        is_operator: bool,
        request: List[RefreshOptionRequest],
        trigger: Literal["default", "http"] = "default",
        system_app: Optional[SystemApp] = None,
    ) -> Dict:
        """Refresh the metadata."""
        if is_operator:
            return await _get_operator_class(key).metadata.refresh(  # type: ignore
                request, trigger, system_app
            )
        else:
            return await _get_resource_class(key).metadata.refresh(
                request, trigger, system_app
            )


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
    if "metadata" not in view_cls.__dict__:
        return  # Skip the base class
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


def _register_resource(
    cls: Type,
    resource_metadata: ResourceMetadata,
    alias_ids: Optional[List[str]] = None,
):
    """Register the operator."""
    _OPERATOR_REGISTRY.register_flow(cls, resource_metadata, alias_ids)
