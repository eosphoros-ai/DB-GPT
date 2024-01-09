from typing import Optional, Any, List
import csv
from dbgpt.rag.chunk import Document
from dbgpt.rag.knowledge.base import (
    KnowledgeType,
    Knowledge,
    ChunkStrategy,
    DocumentType,
)


class CSVKnowledge(Knowledge):
    """CSV Knowledge"""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
        source_column: Optional[str] = None,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize csv with Knowledge arguments.
        Args:
            file_path:(Optional[str]) file path
            knowledge_type:(KnowledgeType) knowledge type
            source_column:(Optional[str]) source column
            encoding:(Optional[str]) csv encoding
            loader:(Optional[Any]) loader
        """
        self._path = file_path
        self._type = knowledge_type
        self._loader = loader
        self._encoding = encoding
        self._source_column = source_column

    def _load(self) -> List[Document]:
        """Load csv document from loader"""
        if self._loader:
            documents = self._loader.load()
        else:
            docs = []
            with open(self._path, newline="", encoding=self._encoding) as csvfile:
                csv_reader = csv.DictReader(csvfile)
                for i, row in enumerate(csv_reader):
                    strs = []
                    for k, v in row.items():
                        if k is None or v is None:
                            continue
                        strs.append(f"{k.strip()}: {v.strip()}")
                    content = "\n".join(strs)
                    try:
                        source = (
                            row[self._source_column]
                            if self._source_column is not None
                            else self._path
                        )
                    except KeyError:
                        raise ValueError(
                            f"Source column '{self._source_column}' not found in CSV file."
                        )
                    metadata = {"source": source, "row": i}
                    doc = Document(content=content, metadata=metadata)
                    docs.append(doc)

            return docs
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
    def type(cls) -> KnowledgeType:
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        return DocumentType.CSV
