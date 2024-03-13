import json
from abc import ABC
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel

from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.agent.resource.resource_loader import ResourceLoader
from dbgpt.util.json_utils import find_json_objects

T = TypeVar("T", None, BaseModel, List[BaseModel])


class ActionOutput(BaseModel):
    content: str
    is_exe_success: bool = True
    view: str = None
    resource_type: Optional[str] = None
    resource_value: Optional[Any] = None

    @staticmethod
    def from_dict(param: Optional[Dict]):
        if not param:
            return None
        return ActionOutput.parse_obj(param)


class Action(ABC, Generic[T]):
    def __init__(self):
        self.resource_loader: ResourceLoader = None

    def init_resource_loader(self, resource_loader: ResourceLoader):
        self.resource_loader = resource_loader

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return None

    @property
    def render_protocal(self):
        raise NotImplementedError("The run method should be implemented in a subclass.")

    def render_prompt(self):
        if self.render_protocal is None:
            return None
        else:
            return self.render_protocal.render_prompt()

    def _create_example(
        self,
        model_type: Union[Type[BaseModel], Type[List[BaseModel]]],
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if model_type is None:
            return None
        origin = get_origin(model_type)
        args = get_args(model_type)
        if origin is None:
            example = {}
            for field_name, field in model_type.__fields__.items():
                field_info = field.field_info
                if field_info.description:
                    example[field_name] = field_info.description
                elif field_info.default:
                    example[field_name] = field_info.default
                else:
                    example[field_name] = ""
            return example
        elif origin is list or origin is List:
            element_type = args[0]
            if issubclass(element_type, BaseModel):
                return [self._create_example(element_type)]
            else:
                raise TypeError("List elements must be BaseModel subclasses")
        else:
            raise ValueError(
                f"Model type {model_type} is not an instance of BaseModel."
            )

    @property
    def out_model_type(self) -> T:
        return None

    @property
    def ai_out_schema(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if self.out_model_type is None:
            return None

        return f"""Please response in the following json format:
            {json.dumps(self._create_example(self.out_model_type), indent=2, ensure_ascii=False)}
        Make sure the response is correct json and can be parsed by Python json.loads. 
        """

    def _ai_mesage_2_json(self, ai_message: str) -> json:
        json_objects = find_json_objects(ai_message)
        json_count = len(json_objects)
        if json_count != 1:
            raise ValueError("Unable to obtain valid output.")
        return json_objects[0]

    def _input_convert(self, ai_message: str, cls: Type[T]) -> Union[T, List[T]]:
        json_result = self._ai_mesage_2_json(ai_message)
        if get_origin(cls) == list:
            inner_type = get_args(cls)[0]
            return [inner_type.parse_obj(item) for item in json_result]
        else:
            return cls.parse_obj(json_result)

    async def a_run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        raise NotImplementedError("The run method should be implemented in a subclass.")
