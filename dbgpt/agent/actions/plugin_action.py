import json
import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from dbgpt.agent.actions.action import Action, ActionOutput, T
from dbgpt.agent.common.schema import Status
from dbgpt.agent.plugin.generator import PluginPromptGenerator
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.agent.resource.resource_plugin_api import ResourcePluginClient
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

logger = logging.getLogger(__name__)


class PluginInput(BaseModel):
    tool_name: str = Field(
        ...,
        description="The name of a tool that can be used to answer the current question or solve the current task.",
    )
    args: dict = Field(
        default={"arg name1": "", "arg name2": ""},
        description="The tool selected for the current target, the parameter information required for execution",
    )
    thought: str = Field(..., description="Summary of thoughts to the user")


class PluginAction(Action[PluginInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._render_protocal = VisPlugin()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return ResourceType.Plugin

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return PluginInput

    @property
    def ai_out_schema(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        out_put_schema = {
            "tool_name": "The name of a tool that can be used to answer the current question or solve the current task.",
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

    async def a_run(
        self,
        ai_message: str,
        plugin_generator: PluginPromptGenerator,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        try:
            param: PluginInput = self._input_convert(ai_message, PluginInput)
        except Exception as e:
            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        try:
            resource_plugin_client: ResourcePluginClient = (
                self.resource_loader.get_resesource_api(self.resource_need)
            )
            if not resource_plugin_client:
                raise ValueError("No implementation of the use of plug-in resources！")
            response_success = True
            status = Status.TODO.value
            err_msg = None
            try:
                status = Status.RUNNING.value
                tool_result = await resource_plugin_client.a_execute_command(
                    param.tool_name, param.args, plugin_generator
                )
                status = Status.COMPLETE.value
            except Exception as e:
                response_success = False
                logger.exception(f"Tool [{param.tool_name}] excute Failed!")
                status = Status.FAILED.value
                err_msg = f"Tool [{param.tool_name}] excute Failed!{str(e)}"

            plugin_param = {
                "name": param.tool_name,
                "args": param.args,
                "status": status,
                "logo": None,
                "result": tool_result,
                "err_msg": err_msg,
            }

            view = await self.render_protocal.display(content=plugin_param)

            return ActionOutput(
                is_exe_success=response_success, content=tool_result, view=view
            )
        except Exception as e:
            logger.exception("Tool Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Tool action run failed!{str(e)}"
            )
