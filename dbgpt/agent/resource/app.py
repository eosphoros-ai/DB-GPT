"""Application Resources for the agent."""

import dataclasses
import uuid
from typing import Any, Dict, List, Optional, Tuple, Type, cast

from dbgpt.agent import AgentMessage, ConversableAgent
from dbgpt.serve.agent.agents.app_agent_manage import get_app_manager
from dbgpt.util import ParameterDescription

from .base import Resource, ResourceParameters, ResourceType


def _get_app_list():
    # Only call this function when the system app is initialized
    apps = get_app_manager().get_dbgpts()
    results = [
        {
            "label": f"{app.app_name}({app.app_code})",
            "key": app.app_code,
            "description": app.app_describe,
        }
        for app in apps
    ]
    return results


def _create_app_resource_parameters() -> Type[ResourceParameters]:
    """Create AppResourceParameters."""

    @dataclasses.dataclass
    class _DynAppResourceParameters(ResourceParameters):
        """Application resource class."""

        app_code: str = dataclasses.field(
            metadata={
                "help": "app code",
                "valid_values": _get_app_list(),
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


class AppResource(Resource[ResourceParameters]):
    """AppResource resource class."""

    def __init__(self, name: str, app_code: str, **kwargs):
        """Initialize AppResource resource."""
        self._resource_name = name
        self._app_code = app_code

        app = get_app_manager().get_app(self._app_code)
        self._app_name = app.app_name
        self._app_desc = app.app_describe

    @property
    def app_desc(self):
        """Return the app description."""
        return self._app_desc

    @property
    def app_name(self):
        """Return the app name."""
        return self._app_name

    @classmethod
    def type(cls) -> ResourceType:
        """Return the resource type."""
        return ResourceType.App

    @property
    def name(self) -> str:
        """Return the resource name."""
        return self._resource_name

    @classmethod
    def resource_parameters_class(cls, **kwargs) -> Type[ResourceParameters]:
        """Return the resource parameters class."""
        return _create_app_resource_parameters()

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
            "{name}：调用此资源与应用 {app_name} 进行交互。" "应用 {app_name} 有什么用？{description}"
        )
        prompt_template_en = (
            "{name}：Call this resource to interact with the application {app_name} ."
            "What is the application {app_name} useful for? {description} "
        )
        template = prompt_template_en if lang == "en" else prompt_template_zh

        return (
            template.format(
                name=self.name, app_name=self._app_name, description=self._app_desc
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

        reply_message = await _start_app(self._app_code, user_input, parent_agent)
        return reply_message.content


async def _start_app(
    app_code: str,
    user_input: str,
    sender: ConversableAgent,
    conv_uid: Optional[str] = None,
) -> AgentMessage:
    """Start App By AppResource."""
    conv_uid = str(uuid.uuid4()) if conv_uid is None else conv_uid
    gpts_app = get_app_manager().get_app(app_code)
    app_agent = await get_app_manager().create_agent_by_app_code(
        gpts_app, conv_uid=conv_uid
    )

    agent_message = AgentMessage(
        content=user_input,
        current_goal=user_input,
        context={
            "conv_uid": conv_uid,
        },
        rounds=0,
    )
    reply_message: AgentMessage = await app_agent.generate_reply(
        received_message=agent_message, sender=sender
    )

    return reply_message
