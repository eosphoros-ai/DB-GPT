"""Wraps the third-party language model embeddings to the common interface."""

from typing import TYPE_CHECKING, List

from dbgpt.core import Embeddings

if TYPE_CHECKING:
    from langchain.embeddings.base import Embeddings as LangChainEmbeddings


class WrappedEmbeddings(Embeddings):
    """Wraps the third-party language model embeddings to the common interface."""

    def __init__(self, embeddings: "LangChainEmbeddings") -> None:
        """Create a new WrappedEmbeddings."""
        self._embeddings = embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""
        return self._embeddings.embed_query(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous Embed search docs."""
        return await self._embeddings.aembed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous Embed query text."""
        return await self._embeddings.aembed_query(text)
