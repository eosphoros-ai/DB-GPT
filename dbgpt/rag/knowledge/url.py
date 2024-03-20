"""URL Knowledge."""
from typing import Any, List, Optional

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import ChunkStrategy, Knowledge, KnowledgeType


class URLKnowledge(Knowledge):
    """URL Knowledge."""

    def __init__(
        self,
        url: str = "",
        knowledge_type: KnowledgeType = KnowledgeType.URL,
        source_column: Optional[str] = None,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Create URL Knowledge with Knowledge arguments.

        Args:
            url(str,  optional): url
            knowledge_type(KnowledgeType, optional): knowledge type
            source_column(str, optional): source column
            encoding(str, optional): csv encoding
            loader(Any, optional): loader
        """
        self._path = url or None
        self._type = knowledge_type
        self._loader = loader
        self._encoding = encoding
        self._source_column = source_column

    def _load(self) -> List[Document]:
        """Fetch URL document from loader."""
        if self._loader:
            documents = self._loader.load()
        else:
            from langchain.document_loaders import WebBaseLoader

            if self._path is not None:
                web_reader = WebBaseLoader(web_path=self._path)
                documents = web_reader.load()
            else:
                # Handle the case where self._path is None
                raise ValueError("web_path cannot be None")
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
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
    def type(cls):
        """Return knowledge type."""
        return KnowledgeType.URL
