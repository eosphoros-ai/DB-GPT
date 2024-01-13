from typing import Any, List, Optional

from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import ChunkStrategy, Knowledge, KnowledgeType


class StringKnowledge(Knowledge):
    """String Knowledge"""

    def __init__(
        self,
        text: str = None,
        knowledge_type: KnowledgeType = KnowledgeType.TEXT,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Knowledge arguments.
        Args:
            text:(str) text
            knowledge_type:(KnowledgeType) knowledge type
            encoding:(encoding) csv encoding
            loader:(loader) loader
        """
        self._text = text
        self._type = knowledge_type
        self._loader = loader
        self._encoding = encoding

    def _load(self) -> List[Document]:
        """load raw text from loader"""
        metadata = {"source": "raw text"}
        docs = [Document(content=self._text, metadata=metadata)]
        return docs

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    def default_chunk_strategy(cls) -> ChunkStrategy:
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls):
        return KnowledgeType.TEXT
