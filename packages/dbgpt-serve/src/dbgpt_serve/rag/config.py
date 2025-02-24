from dataclasses import dataclass, field
from typing import Optional

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.util.i18n_utils import _
from dbgpt_serve.core import BaseServeConfig

APP_NAME = "rag"
SERVE_APP_NAME = "dbgpt_rag"
SERVE_APP_NAME_HUMP = "dbgpt_rag"
SERVE_CONFIG_KEY_PREFIX = "dbgpt_rag"
SERVE_SERVICE_COMPONENT_NAME = f"{SERVE_APP_NAME}_service"


@auto_register_resource(
    label=_("RAG Serve Configurations"),
    category=ResourceCategory.RAG,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("This configuration is for the RAG serve module."),
    show_in_ui=False,
)
@dataclass
class ServeConfig(BaseServeConfig):
    """Parameters for the serve command"""

    __type__ = APP_NAME

    embedding_model: Optional[str] = field(
        default="None",
        metadata={"help": _("Embedding Model")},
    )
    rerank_model: Optional[str] = field(
        default="None",
        metadata={"help": _("Embedding Model")},
    )
    chunk_size: Optional[int] = field(
        default=500,
        metadata={"help": _("Whether to verify the SSL certificate of the database")},
    )
    chunk_overlap: Optional[int] = field(
        default=50,
        metadata={
            "help": _(
                "The default thread pool size, If None, use default config of python "
                "thread pool"
            )
        },
    )
    similarity_top_k: Optional[int] = field(
        default=10,
        metadata={"help": _("knowledge search top k")},
    )
    similarity_score_threshold: Optional[int] = field(
        default=0.0,
        metadata={"help": _("knowledge search top similarity score")},
    )
    query_rewrite: Optional[bool] = field(
        default=False,
        metadata={"help": _("knowledge search rewrite")},
    )
    max_chunks_once_load: Optional[int] = field(
        default=10,
        metadata={"help": _("knowledge max chunks once load")},
    )
    max_threads: Optional[int] = field(
        default=1,
        metadata={"help": _("knowledge max load thread")},
    )
    rerank_top_k: Optional[int] = field(
        default=3,
        metadata={"help": _("knowledge rerank top k")},
    )


@dataclass
class GraphRagServeConfig:
    """Graph_Rag configuration."""
