import json
import logging
from typing import Any, Dict, List, Optional, Union

import requests
from pydantic import BaseModel, Field
from requests.exceptions import HTTPError

from dbgpt.agent.actions.action import Action, ActionOutput, T
from dbgpt.agent.common.schema import Status
from dbgpt.agent.plugin.generator import PluginPromptGenerator
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

logger = logging.getLogger(__name__)


class IndicatorInput(BaseModel):
    indicator_name: str = Field(
        ...,
        description="The name of a indicator.",
    )
    api: str = Field(
        ...,
        description="The api of a indicator.",
    )
    method: str = Field(
        ...,
        description="The api of a indicator request method.",
    )
    args: dict = Field(
        default={"arg name1": "", "arg name2": ""},
        description="The api selected for the current target, the parameter information required for execution",
    )
    thought: str = Field(..., description="Summary of thoughts to the user")


class IndicatorAction(Action[IndicatorInput]):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._render_protocal = VisPlugin()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return ResourceType.Knowledge

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return IndicatorInput

    @property
    def ai_out_schema(self) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        out_put_schema = {
            "indicator_name": "The name of a indicator that can be used to answer the current question or solve the current task.",
            "api": "",
            "method": "",
            "args": {
                "arg name1": "Parameters in api definition",
                "arg name2": "Parameters in api definition",
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
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        try:
            param: IndicatorInput = self._input_convert(ai_message, IndicatorInput)
        except Exception as e:
            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        try:
            status = Status.COMPLETE.value
            response_success = True
            err_msg = None
            resp_text = ""
            try:
                status = Status.RUNNING.value
                if param.method.lower() == "get":
                    response = requests.get(param.api, params=param.args)
                elif param.method.lower() == "post":
                    response = requests.post(param.api, json=param.args)
                else:
                    response = requests.request(
                        param.method.lower(), param.api, json=param.args
                    )
                response.raise_for_status()
                resp_text = response.text
            except HTTPError as http_err:
                print(f"HTTP error occurred: {http_err}")
            except Exception as e:
                response_success = False
                logger.exception(f"API [{param.indicator_name}] excute Failed!")
                status = Status.FAILED.value
                err_msg = f"API [{param.api}] request Failed!{str(e)}"

            api_param = {
                "name": param.api,
                "args": param.args,
                "status": status,
                "logo": None,
                "result": resp_text,
                "err_msg": err_msg,
            }

            view = await self.render_protocal.disply(content=api_param)

            return ActionOutput(
                is_exe_success=response_success, content=resp_text, view=view
            )
        except Exception as e:
            logger.exception("Indicator Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Indicator action run failed!{str(e)}"
            )
