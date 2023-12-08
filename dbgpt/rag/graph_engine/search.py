from abc import ABC, abstractmethod
from enum import Enum


class SearchMode(str, Enum):
    """Query mode enum for Knowledge Graphs.

    Can be passed as the enum struct, or as the underlying string.

    Attributes:
        KEYWORD ("keyword"): Default query mode, using keywords to find triplets.
        EMBEDDING ("embedding"): Embedding mode, using embeddings to find
            similar triplets.
        HYBRID ("hybrid"): Hyrbid mode, combining both keywords and embeddings
            to find relevant triplets.
    """

    KEYWORD = "keyword"
    EMBEDDING = "embedding"
    HYBRID = "hybrid"


class BaseSearch(ABC):
    """Base Search."""

    async def search(self, query: str):
        """Retrieve nodes given query.

        Args:
            query (QueryType): Either a query string or
                a QueryBundle object.

        """
        # if isinstance(query, str):
        return await self._search(query)

    @abstractmethod
    async def _search(self, query: str):
        """search nodes given query.

        Implemented by the user.

        """
        pass
