from typing import Optional, Any, List

from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import Knowledge, KnowledgeType, ChunkStrategy


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
        """Initialize with Knowledge arguments."""
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
            with open(self._path, 'rb') as file:
                reader = pypdf.PdfReader(file)
                for page_num in range(len(reader.pages)):
                    page = reader.pages[page_num]
                    pages.append((page.extract_text(), page_num))

            cleaned_pages = []
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
                cleaned_pages.append(page)
                metadata = {"source": self._path, "page": page_num}
                text = "\f".join(cleaned_pages)
                document = Document(content=text, metadata=metadata)
                documents.append(document)
            return documents
        return [Document.langchain2doc(lc_document) for lc_document in documents]

    def support_chunk_strategy(self):
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PAGE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]
