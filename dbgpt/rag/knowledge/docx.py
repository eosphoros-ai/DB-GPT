from typing import Optional, Any, List

from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import KnowledgeType, Knowledge, ChunkStrategy
import docx


class DocxKnowledge(Knowledge):
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
        """Load docx document from loader"""
        if self._loader:
            documents = self._loader.load()
        else:
            docs = []
            doc = docx.Document(self._path)
            content = []
            for i in range(len(doc.paragraphs)):
                para = doc.paragraphs[i]
                text = para.text
                content.append(text)
            docs.append(
                Document(content="\n".join(content), metadata={"source": self._path})
            )
            return docs
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    def support_chunk_strategy(self):
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PARAGRAPH,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    def default_chunk_strategy(self) -> ChunkStrategy:
        return ChunkStrategy.CHUNK_BY_SIZE
