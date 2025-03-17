from dataclasses import dataclass, field
from typing import Optional

from dbgpt.util.i18n_utils import _
from dbgpt_app.scene import ChatScene
from dbgpt_serve.core.config import (
    BaseGPTsAppMemoryConfig,
    GPTsAppCommonConfig,
    TokenBufferGPTsAppMemoryConfig,
)


@dataclass
class ChatNormalConfig(GPTsAppCommonConfig):
    """Chat Normal Configuration"""

    name = ChatScene.ChatNormal.value()
    memory: Optional[BaseGPTsAppMemoryConfig] = field(
        default_factory=lambda: TokenBufferGPTsAppMemoryConfig(
            max_token_limit=20 * 1024
        ),
        metadata={"help": _("Memory configuration")},
    )
