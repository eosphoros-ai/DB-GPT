from typing import Optional

from ..base import Vis


class VisCode(Vis):
    async def generate_content(self, **kwargs) -> Optional[str]:
        param = {
            "exit_success": kwargs["exit_success"],
            "language": kwargs["language"],
            "code": kwargs["code"],
            "log": kwargs.get("log", None),
        }
        return param

    @classmethod
    def vis_tag(cls):
        return "vis-code"
