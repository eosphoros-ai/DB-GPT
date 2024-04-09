"""Plugin Action Module."""
import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

from ..core.schema import Status
from ..plugin.generator import PluginPromptGenerator
from ..resource.resource_api import AgentResource, ResourceType
from ..resource.resource_plugin_api import ResourcePluginClient
from .action import Action, ActionOutput

logger = logging.getLogger(__name__)


class PluginInput(BaseModel):
    """Plugin input model."""

    tool_name: str = Field(
        ...,
        description="The name of a tool that can be used to answer the current question"
        " or solve the current task.",
    )
    args: dict = Field(
        default={"arg name1": "", "arg name2": ""},
        description="The tool selected for the current target, the parameter "
        "information required for execution",
    )
    thought: str = Field(..., description="Summary of thoughts to the user")


class PluginAction(Action[PluginInput]):
    """Plugin action class."""

    def __init__(self):
        """Create a plugin action."""
        super().__init__()
        self._render_protocol = VisPlugin()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return ResourceType.Plugin

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Return the output model type."""
        return PluginInput

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        out_put_schema = {
            "tool_name": "The name of a tool that can be used to answer the current "
            "question or solve the current task.",
            "args": {
                "arg name1": "arg value1",
                "arg name2": "arg value2",
            },
            "thought": "Summary of thoughts to the user",
        }

        return f"""Please response in the following json format:
        {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
        Make sure the response is correct json and can be parsed by Python json.loads.
        """

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the plugin action.

        Args:
            ai_message (str): The AI message.
            resource (Optional[AgentResource], optional): The resource. Defaults to
                None.
            rely_action_out (Optional[ActionOutput], optional): The rely action output.
                Defaults to None.
            need_vis_render (bool, optional): Whether need visualization rendering.
                Defaults to True.
        """
        plugin_generator: Optional[PluginPromptGenerator] = kwargs.get(
            "plugin_generator", None
        )
        if not plugin_generator:
            raise ValueError("No plugin generator found!")
        try:
            param: PluginInput = self._input_convert(ai_message, PluginInput)
        except Exception as e:
            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        try:
            if not self.resource_loader:
                raise ValueError("No resource_loader found!")
            resource_plugin_client: Optional[
                ResourcePluginClient
            ] = self.resource_loader.get_resource_api(
                self.resource_need, ResourcePluginClient
            )
            if not resource_plugin_client:
                raise ValueError("No implementation of the use of plug-in resources！")
            response_success = True
            status = Status.RUNNING.value
            err_msg = None
            try:
                tool_result = await resource_plugin_client.execute_command(
                    param.tool_name, param.args, plugin_generator
                )
                status = Status.COMPLETE.value
            except Exception as e:
                response_success = False
                logger.exception(f"Tool [{param.tool_name}] execute failed!")
                status = Status.FAILED.value
                err_msg = f"Tool [{param.tool_name}] execute failed! {str(e)}"
                tool_result = err_msg

            plugin_param = {
                "name": param.tool_name,
                "args": param.args,
                "status": status,
                "logo": None,
                "result": tool_result,
                "err_msg": err_msg,
            }
            if not self.render_protocol:
                raise NotImplementedError("The render_protocol should be implemented.")

            view = await self.render_protocol.display(content=plugin_param)

            return ActionOutput(
                is_exe_success=response_success, content=tool_result, view=view
            )
        except Exception as e:
            logger.exception("Tool Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Tool action run failed!{str(e)}"
            )
