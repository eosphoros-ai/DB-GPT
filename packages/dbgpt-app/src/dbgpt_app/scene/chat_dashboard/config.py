from dataclasses import dataclass, field

from dbgpt.util.i18n_utils import _
from dbgpt_app.scene import ChatScene
from dbgpt_serve.core.config import GPTsAppCommonConfig


@dataclass
class ChatDashboardConfig(GPTsAppCommonConfig):
    """Chat Dashboard Configuration"""

    name = ChatScene.ChatDashboard.value()
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
