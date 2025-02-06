"""Base Assembler."""

from abc import ABC, abstractmethod
from typing import Any, List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.transformer.base import ExtractorBase
from dbgpt.util.tracer import root_tracer

from ..chunk_manager import ChunkManager, ChunkParameters


class BaseAssembler(ABC):
    """Base Assembler."""

    def __init__(
        self,
        knowledge: Knowledge,
        chunk_parameters: Optional[ChunkParameters] = None,
        extractor: Optional[ExtractorBase] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Assembler arguments.

        Args:
            knowledge(Knowledge): Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            extractor(Optional[ExtractorBase]):  ExtractorBase to use for summarization.
        """
        self._knowledge = knowledge
        self._chunk_parameters = chunk_parameters or ChunkParameters()
        self._extractor = extractor
        self._chunk_manager = ChunkManager(
            knowledge=self._knowledge, chunk_parameter=self._chunk_parameters
        )
        self._chunks: List[Chunk] = []
        metadata = {
            "knowledge_cls": (
                self._knowledge.__class__.__name__ if self._knowledge else None
            ),
            "knowledge_type": self._knowledge.type().value if self._knowledge else None,
            "path": (
                self._knowledge._path
                if self._knowledge and hasattr(self._knowledge, "_path")
                else None
            ),
            "chunk_parameters": self._chunk_parameters.dict(),
        }
        with root_tracer.start_span("BaseAssembler.load_knowledge", metadata=metadata):
            self.load_knowledge(self._knowledge)

    def load_knowledge(self, knowledge: Knowledge) -> None:
        """Load knowledge Pipeline."""
        if not knowledge:
            raise ValueError("knowledge must be provided.")
        with root_tracer.start_span("BaseAssembler.knowledge.load"):
            documents = knowledge.load()
        with root_tracer.start_span("BaseAssembler.chunk_manager.split"):
            self._chunks = self._chunk_manager.split(documents)

    @abstractmethod
    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        """Return a retriever."""

    @abstractmethod
    def persist(self, **kwargs: Any) -> List[str]:
        """Persist chunks.

        Returns:
            List[str]: List of persisted chunk ids.
        """

    async def apersist(self, **kwargs: Any) -> List[str]:
        """Persist chunks.

        Returns:
            List[str]: List of persisted chunk ids.
        """
        raise NotImplementedError

    def get_chunks(self) -> List[Chunk]:
        """Return chunks."""
        return self._chunks
