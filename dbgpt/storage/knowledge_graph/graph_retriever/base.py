"""Graph retriever base class."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Tuple

from dbgpt.storage.graph_store.graph import Graph

logger = logging.getLogger(__name__)


class GraphRetrieverBase(ABC):
    """Graph retriever base class."""

    @abstractmethod
    async def retrieve(self, input: Any) -> Tuple[Graph, Any]:
        """Retrieve from graph database."""
