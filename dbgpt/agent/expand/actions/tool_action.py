"""Plugin Action Module."""

import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

from ...core.action.base import Action, ActionOutput
from ...core.schema import Status
from ...resource.base import AgentResource, ResourceType
from ...resource.tool.pack import ToolPack

logger = logging.getLogger(__name__)


class ToolInput(BaseModel):
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


class ToolAction(Action[ToolInput]):
    """Tool action class."""

    def __init__(self, **kwargs):
        """Tool action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisPlugin()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return ResourceType.Tool

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Return the output model type."""
        return ToolInput

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        out_put_schema = {
            "thought": "Summary of thoughts to the user",
            "tool_name": "The name of a tool that can be used to answer the current "
            "question or solve the current task.",
            "args": {
                "arg name1": "arg value1",
                "arg name2": "arg value2",
            },
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
        try:
            param: ToolInput = self._input_convert(ai_message, ToolInput)
        except Exception as e:
            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        try:
            tool_packs = ToolPack.from_resource(self.resource)
            if not tool_packs:
                raise ValueError("The tool resource is not found！")
            tool_pack = tool_packs[0]
            response_success = True
            status = Status.RUNNING.value
            err_msg = None
            try:
                tool_result = await tool_pack.async_execute(
                    resource_name=param.tool_name, **param.args
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
                "result": str(tool_result),
                "err_msg": err_msg,
            }
            if not self.render_protocol:
                raise NotImplementedError("The render_protocol should be implemented.")

            view = await self.render_protocol.display(content=plugin_param)

            return ActionOutput(
                is_exe_success=response_success,
                content=str(tool_result),
                view=view,
                observations=str(tool_result),
            )
        except Exception as e:
            logger.exception("Tool Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Tool action run failed!{str(e)}"
            )
