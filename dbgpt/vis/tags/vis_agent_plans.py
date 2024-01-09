from typing import Optional
from ..base import Vis


class VisAgentPlans(Vis):
    async def generate_content(self, **kwargs) -> Optional[str]:
        param = {
            "name": kwargs["name"],
            "num": kwargs["sub_task_num"],
            "status": kwargs["status"],
            "agent": kwargs.get("sub_task_agent", None),
            "markdown": kwargs.get("markdown", None),
        }
        return param

    @classmethod
    def vis_tag(cls):
        return "vis-agent-plans"
