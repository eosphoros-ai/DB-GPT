"""Indicator Agent action."""

import ipaddress
import json
import logging
from typing import Optional
from urllib.parse import urlparse

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
        self._blocked_hosts = {
            "169.254.169.254",
            "metadata.google.internal",
            "metadata.goog",
            "localhost",
            "127.0.0.1",
            "::1",
        }
        self._allowed_methods = {"GET", "POST"}

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

    def _validate_request(self, url: str, method: str) -> Optional[str]:
        """Validate URL and method to prevent SSRF attacks."""
        try:
            parsed = urlparse(url)

            if parsed.scheme not in {"http", "https"}:
                return f"Scheme '{parsed.scheme}' not allowed"

            if parsed.hostname in self._blocked_hosts:
                return f"Hostname '{parsed.hostname}' is blocked"

            if parsed.hostname:
                try:
                    ip = ipaddress.ip_address(parsed.hostname)
                    if (
                        ip.is_private
                        or ip.is_loopback
                        or ip.is_link_local
                        or ip.is_multicast
                    ):
                        return f"Private/internal IP '{parsed.hostname}' is blocked"
                except ValueError:
                    pass

            if any(
                p in parsed.hostname.lower() for p in ["internal", "local", "intranet"]
            ):
                return f"Hostname pattern '{parsed.hostname}' is blocked"

            if method.upper() not in self._allowed_methods:
                return f"Method '{method}' not allowed"

            return None
        except Exception as e:
            return f"URL validation error: {e}"

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

        try:
            param: IndicatorInput = self._input_convert(ai_message, IndicatorInput)
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        if error := self._validate_request(param.api, param.method):
            logger.warning(f"Blocked request: {error}")
            return ActionOutput(
                is_exe_success=False, content=f"Request blocked: {error}"
            )

        try:
            if param.method.lower() == "get":
                response = requests.get(
                    param.api,
                    params=param.args,
                    headers=self.build_headers(),
                    timeout=10,
                    allow_redirects=False,
                )
            elif param.method.lower() == "post":
                response = requests.post(
                    param.api,
                    json=param.args,
                    headers=self.build_headers(),
                    timeout=10,
                    allow_redirects=False,
                )
            else:
                return ActionOutput(
                    is_exe_success=False,
                    content=f"Method '{param.method}' not supported",
                )

            response.raise_for_status()
            logger.info(f"API:{param.api}\nResult:{response.text}")

            plugin_param = {
                "name": param.indicator_name,
                "args": param.args,
                "status": Status.COMPLETE.value,
                "logo": None,
                "result": response.text,
                "err_msg": None,
            }

            view = (
                await self.render_protocol.display(content=plugin_param)
                if self.render_protocol
                else response.text
            )

            return ActionOutput(is_exe_success=True, content=response.text, view=view)

        except Exception as e:
            logger.exception(f"API [{param.indicator_name}] failed: {e}")
            error_msg = f"API request failed: {str(e)}"

            plugin_param = {
                "name": param.indicator_name,
                "args": param.args,
                "status": Status.FAILED.value,
                "logo": None,
                "result": "",
                "err_msg": error_msg,
            }

            view = (
                await self.render_protocol.display(content=plugin_param)
                if self.render_protocol
                else error_msg
            )

            return ActionOutput(is_exe_success=False, content=error_msg, view=view)
