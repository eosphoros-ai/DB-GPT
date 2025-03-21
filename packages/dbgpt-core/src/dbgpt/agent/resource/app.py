"""Application Resources for the agent."""

import dataclasses
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type, cast

from dbgpt._private.pydantic import BaseModel
from dbgpt.agent import AgentMessage, ConversableAgent
from dbgpt.util import ParameterDescription
from dbgpt.util.i18n_utils import _

from .base import Resource, ResourceParameters, ResourceType


class AppInfo(BaseModel):
    code: str
    name: str
    desc: str


class AppResource(Resource[ResourceParameters]):
    """AppResource resource class."""

    def __init__(self, name: str, **kwargs):
        """Initialize AppResource resource."""
        self._resource_name = name

    @property
    @abstractmethod
    def app_desc(self):
        """Return the app description."""

    @property
    @abstractmethod
    def app_name(self):
        """Return the app name."""

    @abstractmethod
    async def _start_app(
        self,
        user_input: str,
        sender: ConversableAgent,
        conv_uid: Optional[str] = None,
    ) -> AgentMessage:
        """start the app"""

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.App

    @property
    def name(self) -> str:
        """Return the resource name."""
        return self._resource_name

    @classmethod
    def _get_app_list(cls) -> List[AppInfo]:
        """Get the current app list"""

    @classmethod
    def resource_parameters_class(cls, **kwargs) -> Type[ResourceParameters]:
        @dataclasses.dataclass
        class _DynAppResourceParameters(ResourceParameters):
            """Application resource class."""

            apps = cls._get_app_list()
            valid_values = [
                {
                    "label": f"{app.name}({app.code})",
                    "key": app.code,
                    "description": app.desc,
                }
                for app in apps
            ]

            app_code: str = dataclasses.field(
                metadata={
                    "help": _("App code"),
                    "valid_values": valid_values,
                },
            )

            @classmethod
            def to_configurations(
                cls,
                parameters: Type["ResourceParameters"],
                version: Optional[str] = None,
                **kwargs,
            ) -> Any:
                """Convert the parameters to configurations."""
                conf: List[ParameterDescription] = cast(
                    List[ParameterDescription], super().to_configurations(parameters)
                )
                version = version or cls._resource_version()
                if version != "v1":
                    return conf
                # Compatible with old version
                for param in conf:
                    if param.param_name == "app_code":
                        return param.valid_values or []
                return []

            @classmethod
            def from_dict(
                cls, data: dict, ignore_extra_fields: bool = True
            ) -> ResourceParameters:
                """Create a new instance from a dictionary."""
                copied_data = data.copy()
                if "app_code" not in copied_data and "value" in copied_data:
                    copied_data["app_code"] = copied_data.pop("value")
                return super().from_dict(
                    copied_data, ignore_extra_fields=ignore_extra_fields
                )

        return _DynAppResourceParameters

    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs,
    ) -> Tuple[str, Optional[Dict]]:
        """Get the prompt."""
        prompt_template_zh = (
            "{name}：调用此资源与应用 {app_name} 进行交互。"
            "应用 {app_name} 有什么用？{description}"
        )
        prompt_template_en = (
            "{name}：Call this resource to interact with the application {app_name} ."
            "What is the application {app_name} useful for? {description} "
        )
        template = prompt_template_en if lang == "en" else prompt_template_zh

        return (
            template.format(
                name=self.name, app_name=self.app_name, description=self.app_desc
            ),
            None,
        )

    @property
    def is_async(self) -> bool:
        """Return whether the tool is asynchronous."""
        return True

    def execute(self, *args, resource_name: Optional[str] = None, **kwargs) -> Any:
        """Execute the resource."""
        if self.is_async:
            raise RuntimeError("Sync execution is not supported")

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
        user_input: Optional[str] = kwargs.get("user_input")
        parent_agent: Optional[ConversableAgent] = kwargs.get("parent_agent")

        if user_input is None:
            raise RuntimeError("AppResource async execution user_input is None")
        if parent_agent is None:
            raise RuntimeError("AppResource async execution parent_agent is None")

        reply_message = await self._start_app(user_input, parent_agent)
        return reply_message.content
