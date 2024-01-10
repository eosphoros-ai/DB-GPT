from typing import Optional

from ..base import Vis


class VisPlugin(Vis):
    async def generate_content(self, **kwargs) -> Optional[str]:
        param = {
            "name": kwargs["name"],
            "status": kwargs["status"],
            "logo": kwargs.get("logo", None),
            "result": kwargs.get("result", None),
            "err_msg": kwargs.get("err_msg", None),
        }
        return param

    @classmethod
    def vis_tag(cls):
        return "vis-plugin"
