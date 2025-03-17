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
class ChatKnowledgeConfig(GPTsAppCommonConfig):
    """Chat Knowledge Configuration"""

    name = ChatScene.ChatKnowledge.value()
    knowledge_retrieve_top_k: int = field(
        default=10,
        metadata={
            "help": _("The number of chunks to retrieve from the knowledge space.")
        },
    )
    knowledge_retrieve_rerank_top_k: int = field(
        default=10,
        metadata={"help": _("The number of chunks after reranking.")},
    )
    similarity_score_threshold: float = field(
        default=0.0,
        metadata={"help": _("The minimum similarity score to return from the query.")},
    )
    memory: Optional[BaseGPTsAppMemoryConfig] = field(
        default_factory=lambda: BufferWindowGPTsAppMemoryConfig(
            keep_start_rounds=0, keep_end_rounds=10
        ),
        metadata={"help": _("Memory configuration")},
    )
