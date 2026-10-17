"""Tool resources."""

import asyncio
import dataclasses
import functools
import inspect
import json
from abc import ABC, abstractmethod
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Type,
    Union,
    cast,
    get_type_hints,
)

from pydantic import TypeAdapter

from dbgpt._private.pydantic import BaseModel, Field, model_validator
from dbgpt.util.configure.base import _MISSING
from dbgpt.util.function_utils import parse_param_description, type_to_string

from ..base import (
    EXECUTE_ARGS_TYPE,
    PARSE_EXECUTE_ARGS_FUNCTION,
    Resource,
    ResourceParameters,
    ResourceType,
)

ToolFunc = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]

DB_GPT_TOOL_IDENTIFIER = "dbgpt_tool"


@dataclasses.dataclass
class ToolResourceParameters(ResourceParameters):
    """Tool resource parameters class."""

    pass


class ToolParameter(BaseModel):
    """Parameter for a tool."""

    name: str = Field(..., description="Parameter name")
    title: str = Field(
        ...,
        description="Parameter title, default to the name with the first letter "
        "capitalized",
    )
    type: str = Field(..., description="Parameter type", examples=["string", "integer"])
    description: str = Field(..., description="Parameter description")
    required: bool = Field(True, description="Whether the parameter is required")
    default: Optional[Any] = Field(
        _MISSING, description="Default value for the parameter"
    )
    json_schema: Optional[Dict[str, Any]] = None

    def to_json_schema(self) -> Dict[str, Any]:
        """Use a JSON Schema type, preserving unions and array item types."""
        if self.json_schema is not None:
            schema = dict(self.json_schema)
        elif self.type.startswith("{"):
            schema = json.loads(self.type)
        else:
            types = [part.strip() for part in self.type.split(",")]
            types = [
                kind
                for kind in types
                if kind
                in {"string", "number", "integer", "boolean", "object", "array", "null"}
            ]
            schema = {"type": types[0] if len(types) == 1 else types} if types else {}
            if "array" in types:
                schema["items"] = {}
        schema["description"] = self.description
        return schema

    @model_validator(mode="before")
    @classmethod
    def pre_fill(cls, values):
        """Pre-fill the model."""
        if not isinstance(values, dict):
            return values
        if "title" not in values:
            values["title"] = values["name"].replace("_", " ").title()
        if "description" not in values:
            values["description"] = values["title"]
        return values


class BaseTool(Resource[ToolResourceParameters], ABC):
    """Base class for a tool."""

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.Tool

    @property
    @abstractmethod
    def description(self) -> str:
        """Return the description of the tool."""

    @property
    @abstractmethod
    def args(self) -> Dict[str, ToolParameter]:
        """Return the arguments of the tool."""

    def parameters_schema(self) -> Dict[str, Any]:
        """Share one parameter schema between prompts and native tool calls."""
        properties = {}
        required = []
        for name, parameter in self.args.items():
            schema = parameter.to_json_schema()
            # TypeAdapter references are relative to its own schema root. Each
            # parameter becomes a property of the function's parameter object.
            prefix = name.replace("~", "~0").replace("/", "~1")

            def relocate(value):
                if isinstance(value, dict):
                    return {key: relocate(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [relocate(item) for item in value]
                if isinstance(value, str) and value.startswith("#/$defs/"):
                    return f"#/properties/{prefix}/$defs/" + value[len("#/$defs/") :]
                return value

            properties[name] = relocate(schema)
            if parameter.required:
                required.append(name)
        return {"type": "object", "properties": properties, "required": required}

    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs,
    ):
        """Get the prompt."""
        prompt_template = (
            "{name}: Call this tool to interact with the {name} API. "
            "What is the {name} API useful for? {description} "
            "Parameters: {parameters}"
        )
        prompt_template_zh = (
            "{name}：调用此工具与 {name} API进行交互。{name} API 有什么用？"
            "{description} 参数：{parameters}"
        )
        template = prompt_template if lang == "en" else prompt_template_zh
        if prompt_type == "openai":
            parameters_dict = self.parameters_schema()
            parameters_string = json.dumps(parameters_dict, ensure_ascii=False)
        else:
            parameters = []
            for key, value in self.args.items():
                parameters.append(
                    {
                        "name": key,
                        "type": value.type,
                        "description": value.description,
                        "required": value.required,
                    }
                )
            parameters_string = json.dumps(parameters, ensure_ascii=False)
        return (
            template.format(
                name=self.name,
                description=self.description,
                parameters=parameters_string,
            ),
            None,
        )


class FunctionTool(BaseTool):
    """Function tool.

    Wrap a function as a tool.
    """

    def __init__(
        self,
        name: str,
        func: ToolFunc,
        description: Optional[str] = None,
        args: Optional[Dict[str, Union[ToolParameter, Dict[str, Any]]]] = None,
        args_schema: Optional[Type[BaseModel]] = None,
        parse_execute_args_func: Optional[PARSE_EXECUTE_ARGS_FUNCTION] = None,
    ):
        """Create a tool from a function."""
        if not description:
            description = _parse_docstring(func)
        if not description:
            raise ValueError("The description is required")
        self._name = name
        self._description = cast(str, description)
        self._args: Dict[str, ToolParameter] = _parse_args(func, args, args_schema)
        self._func = func
        self._is_async = asyncio.iscoroutinefunction(func)
        self._parse_execute_args_func = parse_execute_args_func

    @property
    def name(self) -> str:
        """Return the name of the tool."""
        return self._name

    @property
    def description(self) -> str:
        """Return the description of the tool."""
        return self._description

    @property
    def args(self) -> Dict[str, ToolParameter]:
        """Return the arguments of the tool."""
        return self._args

    @property
    def is_async(self) -> bool:
        """Return whether the tool is asynchronous."""
        return self._is_async

    def parse_execute_args(
        self, resource_name: Optional[str] = None, input_str: Optional[str] = None
    ) -> Optional[EXECUTE_ARGS_TYPE]:
        """Parse the execute arguments."""
        if self._parse_execute_args_func is not None:
            return self._parse_execute_args_func(input_str)
        return None

    def execute(
        self,
        *args,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute the tool.

        Args:
            *args: The positional arguments.
            resource_name (str, optional): The tool name to be executed(not used for
            specific tool).
            **kwargs: The keyword arguments.
        """
        if self._is_async:
            raise ValueError("The function is asynchronous")
        return self._func(*args, **kwargs)

    async def async_execute(
        self,
        *args,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Execute the tool asynchronously.

        Args:
            *args: The positional arguments.
            resource_name (str, optional): The tool name to be executed(not used for
            specific tool).
            **kwargs: The keyword arguments.
        """
        if not self._is_async:
            raise ValueError("The function is synchronous")
        return await self._func(*args, **kwargs)


def tool(
    *decorator_args: Union[str, Callable],
    description: Optional[str] = None,
    args: Optional[Dict[str, Union[ToolParameter, Dict[str, Any]]]] = None,
    args_schema: Optional[Type[BaseModel]] = None,
) -> Callable[..., Any]:
    """Create a tool from a function."""

    def _create_decorator(name: str):
        def decorator(func: ToolFunc):
            tool_name = name or func.__name__
            ft = FunctionTool(tool_name, func, description, args, args_schema)

            @functools.wraps(func)
            def sync_wrapper(*f_args, **kwargs):
                return ft.execute(*f_args, **kwargs)

            @functools.wraps(func)
            async def async_wrapper(*f_args, **kwargs):
                return await ft.async_execute(*f_args, **kwargs)

            if asyncio.iscoroutinefunction(func):
                wrapper = async_wrapper
            else:
                wrapper = sync_wrapper
            wrapper._tool = ft  # type: ignore
            setattr(wrapper, DB_GPT_TOOL_IDENTIFIER, True)
            return wrapper

        return decorator

    if len(decorator_args) == 1 and callable(decorator_args[0]):
        # @tool
        old_func = decorator_args[0]
        return _create_decorator(old_func.__name__)(old_func)
    elif len(decorator_args) == 1 and isinstance(decorator_args[0], str):
        # @tool("google_search")
        return _create_decorator(decorator_args[0])
    elif (
        len(decorator_args) == 2
        and isinstance(decorator_args[0], str)
        and callable(decorator_args[1])
    ):
        # @tool("google_search", description="Search on Google")
        return _create_decorator(decorator_args[0])(decorator_args[1])
    elif len(decorator_args) == 0:
        # use function name as tool name
        def _partial(func: ToolFunc):
            return _create_decorator(func.__name__)(func)

        return _partial
    else:
        raise ValueError("Invalid usage of @tool")


def _parse_docstring(func: ToolFunc) -> str:
    """Parse the docstring of the function."""
    docstring = func.__doc__
    if docstring is None:
        return ""
    return docstring.strip()


def _parse_args(
    func: ToolFunc,
    args: Optional[Dict[str, Union[ToolParameter, Dict[str, Any]]]] = None,
    args_schema: Optional[Type[BaseModel]] = None,
) -> Dict[str, ToolParameter]:
    """Parse the arguments of the function."""
    # Check args all values are ToolParameter
    parsed_args = {}
    if args is not None:
        if all(isinstance(v, ToolParameter) for v in args.values()):
            return args  # type: ignore
        if all(isinstance(v, dict) for v in args.values()):
            for k, v in args.items():
                param_name = v.get("name", k)
                param_title = v.get("title", param_name.replace("_", " ").title())
                param_type = v["type"]
                param_description = v.get("description", param_title)
                param_default = v.get("default", _MISSING)
                param_required = v.get("required", param_default is _MISSING)
                parsed_args[k] = ToolParameter(
                    name=param_name,
                    title=param_title,
                    type=param_type,
                    description=param_description,
                    default=param_default,
                    required=param_required,
                )
            return parsed_args
        raise ValueError("args should be a dict of ToolParameter or dict")

    if args_schema is not None:
        return _parse_args_from_schema(args_schema)
    signature = inspect.signature(func)
    try:
        type_hints = get_type_hints(func, include_extras=True)
    except (NameError, TypeError):
        type_hints = {}

    for param in signature.parameters.values():
        real_type = type_hints.get(param.name, param.annotation)
        param_name = param.name
        param_title = param_name.replace("_", " ").title()

        if param.default is not inspect.Parameter.empty:
            param_default = param.default
            param_required = False
        else:
            param_default = _MISSING
            param_required = True
        param_type, _ = type_to_string(real_type, "unknown")
        param_description = parse_param_description(param_name, real_type)
        try:
            parameter_schema = TypeAdapter(real_type).json_schema()
        except (TypeError, ValueError):
            parameter_schema = None
        parsed_args[param_name] = ToolParameter(
            name=param_name,
            title=param_title,
            type=param_type,
            description=param_description,
            default=param_default,
            required=param_required,
            json_schema=parameter_schema,
        )
    return parsed_args


def _parse_args_from_schema(args_schema: Type[BaseModel]) -> Dict[str, ToolParameter]:
    """Parse the arguments from a Pydantic schema."""
    full_schema = args_schema.model_json_schema()
    pydantic_args = full_schema["properties"]
    parsed_args = {}
    for key, value in pydantic_args.items():
        param_name = key
        param_title = value.get("title", param_name.replace("_", " ").title())
        if "type" in value:
            param_type = value["type"]
        elif "anyOf" in value:
            # {"anyOf": [{"type": "string"}, {"type": "null"}]}
            any_of: List[Dict[str, Any]] = value["anyOf"]
            if len(any_of) == 2 and any(t.get("type") == "null" for t in any_of):
                non_null = next(t for t in any_of if t.get("type") != "null")
                param_type = non_null.get("type", json.dumps(non_null))
            else:
                param_type = json.dumps({"anyOf": value["anyOf"]}, ensure_ascii=False)
        elif "$ref" in value:
            param_type = "object"
        else:
            raise ValueError(f"Invalid schema for {key}")
        param_description = value.get("description", param_title)
        param_default = value.get("default", _MISSING)
        param_required = key in full_schema.get("required", [])
        if "$defs" in full_schema:
            value = dict(value, **{"$defs": full_schema["$defs"]})

        parsed_args[key] = ToolParameter(
            name=param_name,
            title=param_title,
            type=param_type,
            description=param_description,
            default=param_default,
            required=param_required,
            json_schema=value,
        )
    return parsed_args
