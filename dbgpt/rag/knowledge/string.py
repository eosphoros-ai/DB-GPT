from typing import Optional, Any, List

from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import KnowledgeType, Knowledge, ChunkStrategy


class StringKnowledge(Knowledge):
    def __init__(
        self,
        text: str = None,
        knowledge_type: KnowledgeType = KnowledgeType.TEXT,
        source_column: Optional[str] = None,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Knowledge arguments."""
        self._text = text
        self._type = knowledge_type
        self._loader = loader
        self._encoding = encoding
        self._source_column = source_column

    def _load(self) -> List[Document]:
        """load raw text from loader"""
        metadata = {"source": "raw text"}
        docs = [Document(content=self._text, metadata=metadata)]
        return docs

    def support_chunk_strategy(self):
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PARAGRAPH,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    def default_chunk_strategy(self) -> ChunkStrategy:
        return ChunkStrategy.CHUNK_BY_SIZE
