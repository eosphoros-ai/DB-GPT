"""Base Action class for defining agent actions."""
import json
from abc import ABC, abstractmethod
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
)

from dbgpt._private.pydantic import (
    BaseModel,
    field_default,
    field_description,
    model_fields,
    model_to_dict,
)
from dbgpt.util.json_utils import find_json_objects

from ...vis.base import Vis
from ..resource.resource_api import AgentResource, ResourceType
from ..resource.resource_loader import ResourceLoader

T = TypeVar("T", bound=Union[BaseModel, List[BaseModel], None])

JsonMessageType = Union[Dict[str, Any], List[Dict[str, Any]]]


class ActionOutput(BaseModel):
    """Action output model."""

    content: str
    is_exe_success: bool = True
    view: Optional[str] = None
    resource_type: Optional[str] = None
    resource_value: Optional[Any] = None

    @classmethod
    def from_dict(
        cls: Type["ActionOutput"], param: Optional[Dict]
    ) -> Optional["ActionOutput"]:
        """Convert dict to ActionOutput object."""
        if not param:
            return None
        return cls.parse_obj(param)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the object to a dictionary."""
        return model_to_dict(self)


class Action(ABC, Generic[T]):
    """Base Action class for defining agent actions."""

    def __init__(self):
        """Create an action."""
        self.resource_loader: Optional[ResourceLoader] = None

    def init_resource_loader(self, resource_loader: Optional[ResourceLoader]):
        """Initialize the resource loader."""
        self.resource_loader = resource_loader

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return None

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return None

    def render_prompt(self) -> Optional[str]:
        """Return the render prompt."""
        if self.render_protocol is None:
            return None
        else:
            return self.render_protocol.render_prompt()

    def _create_example(
        self,
        model_type: Union[Type[BaseModel], List[Type[BaseModel]]],
    ) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        if model_type is None:
            return None
        origin = get_origin(model_type)
        args = get_args(model_type)
        if origin is None:
            example = {}
            single_model_type = cast(Type[BaseModel], model_type)
            for field_name, field in model_fields(single_model_type).items():
                description = field_description(field)
                default_value = field_default(field)
                if description:
                    example[field_name] = description
                elif default_value:
                    example[field_name] = default_value
                else:
                    example[field_name] = ""
            return example
        elif origin is list or origin is List:
            element_type = cast(Type[BaseModel], args[0])
            if issubclass(element_type, BaseModel):
                list_example = self._create_example(element_type)
                typed_list_example = cast(Dict[str, Any], list_example)
                return [typed_list_example]
            else:
                raise TypeError("List elements must be BaseModel subclasses")
        else:
            raise ValueError(
                f"Model type {model_type} is not an instance of BaseModel."
            )

    @property
    def out_model_type(self) -> Optional[Union[Type[T], List[Type[T]]]]:
        """Return the output model type."""
        return None

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        if self.out_model_type is None:
            return None

        json_format_data = json.dumps(
            self._create_example(self.out_model_type), indent=2, ensure_ascii=False
        )
        return f"""Please response in the following json format:
            {json_format_data}
        Make sure the response is correct json and can be parsed by Python json.loads.
        """

    def _ai_message_2_json(self, ai_message: str) -> JsonMessageType:
        json_objects = find_json_objects(ai_message)
        json_count = len(json_objects)
        if json_count != 1:
            raise ValueError("Unable to obtain valid output.")
        return json_objects[0]

    def _input_convert(self, ai_message: str, cls: Type[T]) -> T:
        json_result = self._ai_message_2_json(ai_message)
        if get_origin(cls) == list:
            inner_type = get_args(cls)[0]
            typed_cls = cast(Type[BaseModel], inner_type)
            return [typed_cls.parse_obj(item) for item in json_result]  # type: ignore
        else:
            typed_cls = cast(Type[BaseModel], cls)
            return typed_cls.parse_obj(json_result)

    @abstractmethod
    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
