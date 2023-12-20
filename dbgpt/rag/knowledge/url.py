from typing import Optional, Any, List

from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import KnowledgeType, Knowledge, ChunkStrategy


class URLKnowledge(Knowledge):
    def __init__(
        self,
        url: Optional[str] = None,
        knowledge_type: KnowledgeType = KnowledgeType.URL,
        source_column: Optional[str] = None,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Knowledge arguments.
        Args:
            url:(Optional[str]) url
            knowledge_type:(KnowledgeType) knowledge type
            source_column:(Optional[str]) source column
            encoding:(Optional[str]) csv encoding
            loader:(Optional[Any]) loader
        """
        self._path = url
        self._type = knowledge_type
        self._loader = loader
        self._encoding = encoding
        self._source_column = source_column

    def _load(self) -> List[Document]:
        """Fetch URL document from loader"""
        if self._loader:
            documents = self._loader.load()
        else:
            from langchain.document_loaders import WebBaseLoader

            web_reader = WebBaseLoader(web_path=self._path)
            documents = web_reader.load()
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls):
        return KnowledgeType.URL
