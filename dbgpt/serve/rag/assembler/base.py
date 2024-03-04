from abc import ABC, abstractmethod
from typing import Any, List, Optional

from dbgpt.rag.chunk import Chunk
from dbgpt.rag.chunk_manager import ChunkManager, ChunkParameters
from dbgpt.rag.extractor.base import Extractor
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.util.tracer import root_tracer, trace


class BaseAssembler(ABC):
    """Base Assembler"""

    def __init__(
        self,
        knowledge: Optional[Knowledge] = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        extractor: Optional[Extractor] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Assembler arguments.
        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for chunking.
            extractor: (Optional[Extractor]) Extractor to use for summarization."""
        self._knowledge = knowledge
        self._chunk_parameters = chunk_parameters or ChunkParameters()
        self._extractor = extractor
        self._chunk_manager = ChunkManager(
            knowledge=self._knowledge, chunk_parameter=self._chunk_parameters
        )
        self._chunks = None
        metadata = {
            "knowledge_cls": self._knowledge.__class__.__name__
            if self._knowledge
            else None,
            "knowledge_type": self._knowledge.type().value if self._knowledge else None,
            "path": self._knowledge._path
            if self._knowledge and hasattr(self._knowledge, "_path")
            else None,
            "chunk_parameters": self._chunk_parameters.dict(),
        }
        with root_tracer.start_span("BaseAssembler.load_knowledge", metadata=metadata):
            self.load_knowledge(self._knowledge)

    def load_knowledge(self, knowledge) -> None:
        """Load knowledge Pipeline."""
        with root_tracer.start_span("BaseAssembler.knowledge.load"):
            documents = knowledge.load()
        with root_tracer.start_span("BaseAssembler.chunk_manager.split"):
            self._chunks = self._chunk_manager.split(documents)

    @abstractmethod
    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        """Return a retriever."""

    @abstractmethod
    def persist(self, chunks: List[Chunk]) -> None:
        """Persist chunks."""

    def get_chunks(self) -> List[Chunk]:
        """Return chunks."""
        return self._chunks
