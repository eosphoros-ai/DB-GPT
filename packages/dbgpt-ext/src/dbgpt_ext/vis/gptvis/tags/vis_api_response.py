"""Vis Api Response."""

import json

from dbgpt.agent.core.schema import Status
from dbgpt.vis.base import Vis


class VisApiResponse(Vis):
    """Vis Api Response."""

    @classmethod
    def vis_tag(cls):
        """Vis Api Response."""
        return "vis-api-response"

    def sync_display(self, **kwargs) -> str:
        """Display the content using the vis protocol."""
        content = kwargs.get("content")

        try:
            new_content = {
                "name": content.get("tool_name", ""),
                "args": content.get("tool_args", ""),
                "status": content.get("status", Status.RUNNING.value),
                "logo": content.get("avatar", ""),
                "result": content.get("tool_result", ""),
                "err_msg": content.get("err_msg", ""),
            }
            return f"```{self.vis_tag()}\n{json.dump(new_content, ensure_ascii=False)}\n```"
        except Exception:
            return str(content)
