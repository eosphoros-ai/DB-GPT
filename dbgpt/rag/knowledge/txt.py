"""TXT Knowledge."""
from typing import Any, List, Optional

import chardet

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)


class TXTKnowledge(Knowledge):
    """TXT Knowledge."""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT,
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Create TXT Knowledge with Knowledge arguments.

        Args:
            file_path(str,  optional): file path
            knowledge_type(KnowledgeType, optional): knowledge type
            loader(Any, optional): loader
        """
        self._path = file_path
        self._type = knowledge_type
        self._loader = loader

    def _load(self) -> List[Document]:
        """Load txt document from loader."""
        if self._loader:
            documents = self._loader.load()
        else:
            if not self._path:
                raise ValueError("file path is required")
            with open(self._path, "rb") as f:
                raw_text = f.read()
                result = chardet.detect(raw_text)
                if result["encoding"] is None:
                    text = raw_text.decode("utf-8")
                else:
                    text = raw_text.decode(result["encoding"])
            metadata = {"source": self._path}
            return [Document(content=text, metadata=metadata)]

        return [Document.langchain2doc(lc_document) for lc_document in documents]

    @classmethod
    def support_chunk_strategy(cls):
        """Return support chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy."""
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls) -> KnowledgeType:
        """Return knowledge type."""
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        """Return document type."""
        return DocumentType.TXT
