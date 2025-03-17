from dataclasses import dataclass, field
from typing import Optional

from dbgpt.util.i18n_utils import _
from dbgpt_app.scene import ChatScene
from dbgpt_serve.core.config import (
    BaseGPTsAppMemoryConfig,
    BufferWindowGPTsAppMemoryConfig,
    GPTsAppCommonConfig,
)


@dataclass
class ChatWithDBExecuteConfig(GPTsAppCommonConfig):
    """Chat With DB Execute Configuration"""

    name = ChatScene.ChatWithDbExecute.value()
    schema_retrieve_top_k: int = field(
        default=10,
        metadata={"help": _("The number of tables to retrieve from the database.")},
    )
    schema_max_tokens: int = field(
        default=100 * 1024,
        metadata={
            "help": _(
                "The maximum number of tokens to pass to the model, default 100 * 1024."
                "Just work for the schema retrieval failed, and load all tables schema."
            )
        },
    )
    max_num_results: int = field(
        default=50,
        metadata={"help": _("The maximum number of results to return from the query.")},
    )
    memory: Optional[BaseGPTsAppMemoryConfig] = field(
        default_factory=lambda: BufferWindowGPTsAppMemoryConfig(
            keep_start_rounds=0, keep_end_rounds=10
        ),
        metadata={"help": _("Memory configuration")},
    )
