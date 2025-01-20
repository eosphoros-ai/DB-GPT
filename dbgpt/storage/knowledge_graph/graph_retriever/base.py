"""Graph retriever base class."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Any, Tuple

from pydantic import Field

from dbgpt._private.pydantic import ConfigDict
from dbgpt.core import Chunk
from dbgpt.rag.index.base import IndexStoreBase, IndexStoreConfig
from dbgpt.storage.graph_store.graph import (
    Direction,
    Edge,
    Graph,
    GraphElemType,
    MemoryGraph,
    Vertex,
)

logger = logging.getLogger(__name__)


class GraphRetrieverBase(ABC):
    """Graph retriever base class."""

    @abstractmethod
    async def retrieve(self, input: Any) -> Tuple[Graph, Any]:
        """Retrieve from graph database."""
