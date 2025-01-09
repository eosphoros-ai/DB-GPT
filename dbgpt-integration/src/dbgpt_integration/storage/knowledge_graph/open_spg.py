"""OpenSPG class."""
import logging

from dbgpt._private.pydantic import ConfigDict
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase, KnowledgeGraphConfig

logger = logging.getLogger(__name__)


class OpenSPGConfig(KnowledgeGraphConfig):
    """OpenSPG config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OpenSPG(KnowledgeGraphBase):
    """OpenSPG class."""

    # todo: add OpenSPG implementation
