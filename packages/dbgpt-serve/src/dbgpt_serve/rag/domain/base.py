"""Base class for Domain Knowledge Index."""

from abc import ABC, abstractmethod
from typing import Optional

from dbgpt.core import Chunk
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase
from dbgpt.storage.vector_store.base import VectorStoreBase


class DomainKnowledgeIndex(ABC):
    @abstractmethod
    async def extract(
        self, knowledge: Knowledge, chunk_parameter, **kwargs
    ) -> list[Chunk]:
        raise NotImplementedError

    @abstractmethod
    async def transform(self, chunks: list[Chunk], **kwargs) -> list[Chunk]:
        raise NotImplementedError

    @abstractmethod
    async def load(
        self,
        chunks: list[Chunk],
        vector_store: Optional[VectorStoreBase] = None,
        full_text_store: Optional[FullTextStoreBase] = None,
        kg_store: Optional[KnowledgeGraphBase] = None,
        keywords: bool = True,
        max_chunks_once_load: int = 10,
        max_threads: int = 1,
        **kwargs,
    ) -> list[Chunk]:
        raise NotImplementedError

    async def clean(
        self,
        chunks: list[Chunk],
        node_ids: Optional[list[str]],
        with_keywords: bool = True,
        **kwargs,
    ):
        raise NotImplementedError

    @classmethod
    def domain_type(cls) -> str:
        raise NotImplementedError
