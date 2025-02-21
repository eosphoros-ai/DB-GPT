"""Indicator Agent action."""

import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_api_response import VisApiResponse
from dbgpt.vis.tags.vis_plugin import Vis

from ...core.action.base import Action, ActionOutput
from ...core.schema import Status
from ...resource.base import AgentResource, ResourceType

logger = logging.getLogger(__name__)


class IndicatorInput(BaseModel):
    """Indicator llm out model."""

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
        description="The tool selected for the current target, "
        "the parameter information required for execution",
    )
    thought: str = Field(..., description="Summary of thoughts to the user")
    display: str = Field(None, description="How to display return information")


class IndicatorAction(Action[IndicatorInput]):
    """Indicator Action."""

    def __init__(self, **kwargs):
        """Init indicator action."""
        super().__init__(**kwargs)
        self._render_protocol = VisApiResponse()

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
            "indicator_name": "The name of a tool that can be used to answer the current question or solve the current task.",  # noqa
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

    def build_headers(self):
        """Build headers."""
        return None

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
            logger.info(
                f"_input_convert: {type(self).__name__} ai_message: {ai_message}"
            )
            param: IndicatorInput = self._input_convert(ai_message, IndicatorInput)
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        try:
            status = Status.RUNNING.value
            response_success = True
            response_text = ""
            err_msg = None
            try:
                if param.method.lower() == "get":
                    response = requests.get(
                        param.api, params=param.args, headers=self.build_headers()
                    )
                elif param.method.lower() == "post":
                    response = requests.post(
                        param.api, json=param.args, headers=self.build_headers()
                    )
                else:
                    response = requests.request(
                        param.method.lower(),
                        param.api,
                        data=param.args,
                        headers=self.build_headers(),
                    )
                response_text = response.text
                logger.info(f"API:{param.api}\nResult:{response_text}")
                # If the request returns an error status code, an HTTPError exception
                # is thrown
                response.raise_for_status()
                status = Status.COMPLETE.value
            except HTTPError as http_err:
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
                "result": response_text,
                "err_msg": err_msg,
            }

            view = (
                await self.render_protocol.display(content=plugin_param)
                if self.render_protocol
                else response_text
            )

            return ActionOutput(
                is_exe_success=response_success, content=response_text, view=view
            )
        except Exception as e:
            logger.exception("Indicator Action Run Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Indicator action run failed!{str(e)}"
            )
