"""Interface for embedding models."""

import asyncio
from abc import ABC, abstractmethod
from typing import List


class RerankEmbeddings(ABC):
    """Interface for rerank models."""

    @abstractmethod
    def predict(self, query: str, candidates: List[str]) -> List[float]:
        """Predict the scores of the candidates."""

    async def apredict(self, query: str, candidates: List[str]) -> List[float]:
        """Asynchronously predict the scores of the candidates."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.predict, query, candidates
        )


class Embeddings(ABC):
    """Interface for embedding models.

    Refer to `Langchain Embeddings <https://github.com/langchain-ai/langchain/tree/
    master/libs/langchain/langchain/embeddings>`_.
    """

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed search docs."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed query text."""

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous Embed search docs."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_documents, texts
        )

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous Embed query text."""
        return await asyncio.get_running_loop().run_in_executor(
            None, self.embed_query, text
        )
