from typing import Optional

from webdriver_manager.chrome import ChromeDriverManager

from ..base import Vis


class VisDbgptsFlowResult(Vis):
    @classmethod
    def vis_tag(cls):
        return "dbgpts-result"
