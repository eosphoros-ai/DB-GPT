from typing import Any, List, Optional

from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)


class PDFKnowledge(Knowledge):
    """PDF Knowledge"""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT,
        loader: Optional = None,
        language: Optional[str] = "zh",
        **kwargs: Any,
    ) -> None:
        """Initialize with PDF Knowledge arguments.
        Args:
            file_path:(Optional[str]) file path
            knowledge_type:(KnowledgeType) knowledge type
            loader:(Optional[Any]) loader
        """
        self._path = file_path
        self._type = knowledge_type
        self._loader = loader
        self._language = language

    def _load(self) -> List[Document]:
        """Load pdf document from loader"""
        if self._loader:
            documents = self._loader.load()
        else:
            import pypdf

            pages = []
            documents = []
            with open(self._path, "rb") as file:
                reader = pypdf.PdfReader(file)
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    pages.append((page.extract_text(), page_num))

            # cleaned_pages = []
            for page, page_num in pages:
                lines = page.splitlines()

                cleaned_lines = []
                for line in lines:
                    if self._language == "en":
                        words = list(line)
                    else:
                        words = line.split()
                    digits = [word for word in words if any(i.isdigit() for i in word)]
                    cleaned_lines.append(line)
                page = "\n".join(cleaned_lines)
                # cleaned_pages.append(page)
                metadata = {"source": self._path, "page": page_num}
                # text = "\f".join(cleaned_pages)
                document = Document(content=page, metadata=metadata)
                documents.append(document)
            return documents
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PAGE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls) -> KnowledgeType:
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        return DocumentType.PDF
