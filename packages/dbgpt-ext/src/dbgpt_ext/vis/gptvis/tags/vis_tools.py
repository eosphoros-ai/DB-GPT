"""Vis Plugin."""

import json

from dbgpt.agent.core.schema import Status
from dbgpt.util.json_utils import serialize
from dbgpt.vis.base import Vis


class VisTools(Vis):
    """Vis Plugin."""

    @classmethod
    def vis_tag(cls):
        """Vis Plugin."""
        return "vis-tools"

    def sync_display(self, **kwargs) -> str:
        """Display the content using the vis protocol."""
        content = kwargs.get("content")

        try:
            items = []
            for step in content.get("steps"):
                new_content = {
                    "name": step.get("tool_name", ""),
                    "args": step.get("tool_args", ""),
                    "status": step.get("status", Status.RUNNING.value),
                    "logo": step.get("avatar", ""),
                    "result": step.get("tool_result", ""),
                    "err_msg": step.get("err_msg", ""),
                }
                items.append(
                    f"```{self.vis_tag()}\n{json.dumps(new_content, default=serialize, ensure_ascii=False)}\n```"
                )
            return "\n".join(items)
        except Exception:
            return str(content)
