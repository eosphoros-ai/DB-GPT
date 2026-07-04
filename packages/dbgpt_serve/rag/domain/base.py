"""Base class for Domain Knowledge Index.

Defines the ETL (Extract-Transform-Load) pipeline interface that each data source
must implement. Each domain type (normal, git_repo, yuque, notion, etc.) provides
its own indexing strategy through this abstraction.
"""

from abc import ABC, abstractmethod
from typing import Optional

from dbgpt.core import Chunk
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase
from dbgpt.storage.vector_store.base import VectorStoreBase


class DomainKnowledgeIndex(ABC):
    """Abstract base class for domain-specific knowledge indexing.

    Each data source type (local documents, git repositories, yuque, notion, etc.)
    implements its own ETL pipeline by subclassing this and overriding the
    extract/transform/load methods.

    The factory pattern (DomainKnowledgeIndexFactory) is used to instantiate the
    correct index based on the knowledge space's domain_type.
    """

    @abstractmethod
    async def extract(
        self,
        knowledge: Knowledge,
        chunk_parameter,
        **kwargs,
    ) -> list[Chunk]:
        """Extract knowledge chunks from the data source."""
        raise NotImplementedError

    @abstractmethod
    async def transform(
        self,
        chunks: list[Chunk],
        **kwargs,
    ) -> list[Chunk]:
        """Transform knowledge chunks (enrichment, summarization, etc.)."""
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
        """Load knowledge chunks into storage backends."""
        raise NotImplementedError

    async def clean(
        self,
        chunks: list[Chunk],
        node_ids: Optional[list[str]],
        with_keywords: bool = True,
        **kwargs,
    ):
        """Clean up indexed chunks from storage backends."""
        raise NotImplementedError

    @classmethod
    def domain_type(cls) -> str:
        """Return the domain type identifier for this index."""
        raise NotImplementedError