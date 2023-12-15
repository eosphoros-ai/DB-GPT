from typing import Optional, Any, List

from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import KnowledgeType, Knowledge, ChunkStrategy


class MarkdownKnowledge(Knowledge):
    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Knowledge arguments."""
        self._path = file_path
        self._type = knowledge_type
        self._loader = loader
        self._encoding = encoding

    def _load(self) -> List[Document]:
        """Load markdown document from loader"""
        if self._loader:
            documents = self._loader.load()
        else:
            with open(self._path, encoding=self._encoding, errors="ignore") as f:
                markdown_text = f.read()
                metadata = {"source": self._path}
                documents = [Document(content=markdown_text, metadata=metadata)]
                return documents
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    def support_chunk_strategy(self):
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_MARKDOWN_HEADER,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    def default_chunk_strategy(self) -> ChunkStrategy:
        return ChunkStrategy.CHUNK_BY_MARKDOWN_HEADER
