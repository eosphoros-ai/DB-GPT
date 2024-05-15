"""Indicator Action."""

import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_plugin import Vis, VisPlugin

from ...core.action.base import Action, ActionOutput
from ...core.schema import Status
from ...resource.base import AgentResource, ResourceType

logger = logging.getLogger(__name__)


class IndicatorInput(BaseModel):
    """Indicator input model."""

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
        description="The tool selected for the current target, the parameter "
        "information required for execution",
    )
    thought: str = Field(..., description="Summary of thoughts to the user")


class IndicatorAction(Action[IndicatorInput]):
    """Indicator action class."""

    def __init__(self):
        """Create a indicator action."""
        super().__init__()
        self._render_protocol = VisPlugin()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return ResourceType.Knowledge

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Return the output model type."""
        return IndicatorInput

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        out_put_schema = {
            "indicator_name": "The name of a tool that can be used to answer the "
            "current question or solve the current task.",
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

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
        import requests
        from requests.exceptions import HTTPError

        try:
            input_param = self._input_convert(ai_message, IndicatorInput)
        except Exception as e:
            logger.exception((str(e)))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )
        if isinstance(input_param, list):
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )
        param: IndicatorInput = input_param
        response_success = True
        result: Optional[str] = None
        try:
            status = Status.COMPLETE.value
            err_msg = None
            try:
                status = Status.RUNNING.value
                if param.method.lower() == "get":
                    response = requests.get(param.api, params=param.args)
                elif param.method.lower() == "post":
                    response = requests.post(param.api, data=param.args)
                else:
                    response = requests.request(
                        param.method.lower(), param.api, data=param.args
                    )
                # Raise an HTTPError if the HTTP request returned an unsuccessful
                # status code
                response.raise_for_status()
                result = response.text
            except HTTPError as http_err:
                response_success = False
                print(f"HTTP error occurred: {http_err}")
            except Exception as e:
                response_success = False
                logger.exception(f"API [{param.indicator_name}] excute Failed!")
                status = Status.FAILED.value
                err_msg = f"API [{param.api}] request Failed!{str(e)}"

            plugin_param = {
                "name": param.indicator_name,
                "args": param.args,
                "status": status,
                "logo": None,
                "result": result,
                "err_msg": err_msg,
            }

            if not self.render_protocol:
                raise NotImplementedError("The render_protocol should be implemented.")
            view = await self.render_protocol.display(content=plugin_param)

            return ActionOutput(
                is_exe_success=response_success, content=result, view=view
            )
        except Exception as e:
            logger.exception("Indicator Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Indicator action run failed!{str(e)}"
            )
