from typing import Optional

from ..base import Vis
from webdriver_manager.chrome import ChromeDriverManager


class VisDbgptsFlowResult(Vis):
    @classmethod
    def vis_tag(cls):
        return "dbgpts-result"
