"""OpenSPG class."""

import logging
from dataclasses import dataclass

from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase, KnowledgeGraphConfig

logger = logging.getLogger(__name__)


@dataclass
class OpenSPGConfig(KnowledgeGraphConfig):
    """OpenSPG config."""

    __type__ = "openspg"


class OpenSPG(KnowledgeGraphBase):
    """OpenSPG class."""

    # todo: add OpenSPG implementation
