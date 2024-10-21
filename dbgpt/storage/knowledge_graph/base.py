"""Knowledge graph base class."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import Field

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.rag.index.base import IndexStoreBase, IndexStoreConfig
from dbgpt.storage.graph_store.graph import Graph

logger = logging.getLogger(__name__)


class KnowledgeGraphConfig(IndexStoreConfig):
    """Knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")


class KnowledgeGraphBase(IndexStoreBase, ABC):
    """Knowledge graph base class."""

    @abstractmethod
    def get_config(self) -> KnowledgeGraphConfig:
        """Get the knowledge graph config."""

    @abstractmethod
    def query_graph(self, limit: Optional[int] = None) -> Graph:
        """Get graph data."""

    @abstractmethod
    def delete_by_ids(self, ids: str) -> List[str]:
        """Delete document by ids."""


class ParagraphChunk(Chunk):
    """Loaded chunk, used in GraphRAG."""

    chunk_parent_id: str = Field(default=None, description="id of parent chunk")
    chunk_parent_name: str = Field(default=None, description="parent chunk name")
    parent_content: str = Field(default=None, description="parent chunk text content")
    parent_is_document: bool = Field(
        default=False, description="is parent chunk a document"
    )
