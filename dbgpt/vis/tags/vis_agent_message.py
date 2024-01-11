from typing import Optional

from ..base import Vis


class VisAgentMessages(Vis):
    async def generate_content(self, **kwargs) -> Optional[str]:
        param = {
            "sender": kwargs["sender"],
            "receiver": kwargs["receiver"],
            "model": kwargs["model"],
            "markdown": kwargs.get("markdown", None),
        }
        return param

    @classmethod
    def vis_tag(cls):
        return "vis-agent-messages"
