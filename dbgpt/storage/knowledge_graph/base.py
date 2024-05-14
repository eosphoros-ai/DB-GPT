"""Knowledge graph base class."""
import logging
from abc import ABC

from dbgpt._private.pydantic import ConfigDict
from dbgpt.rag.index.base import IndexStoreBase
from dbgpt.rag.index.base import IndexStoreConfig

logger = logging.getLogger(__name__)


class KnowledgeGraphConfig(IndexStoreConfig):
    """Knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class KnowledgeGraphBase(IndexStoreBase, ABC):
    """Knowledge graph base class."""

    def delete_by_ids(self, ids: str):
        raise Exception("Delete document not supported by knowledge graph")
