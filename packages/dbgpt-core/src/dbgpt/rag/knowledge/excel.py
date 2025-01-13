"""Excel Knowledge."""

from typing import Any, Dict, List, Optional, Union

import pandas as pd

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)


class ExcelKnowledge(Knowledge):
    """Excel Knowledge."""

    def __init__(
        self,
        file_path: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
        source_column: Optional[str] = None,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        **kwargs: Any,
    ) -> None:
        """Create xlsx Knowledge with Knowledge arguments.

        Args:
            file_path(str,  optional): file path
            knowledge_type(KnowledgeType, optional): knowledge type
            source_column(str, optional): source column
            encoding(str, optional): csv encoding
            loader(Any, optional): loader
        """
        super().__init__(
            path=file_path,
            knowledge_type=knowledge_type,
            data_loader=loader,
            metadata=metadata,
            **kwargs,
        )
        self._encoding = encoding
        self._source_column = source_column

    def _load(self) -> List[Document]:
        """Load csv document from loader."""
        if self._loader:
            documents = self._loader.load()
        else:
            docs = []
            if not self._path:
                raise ValueError("file path is required")

            excel_file = pd.ExcelFile(self._path)
            sheet_names = excel_file.sheet_names
            for sheet_name in sheet_names:
                df = excel_file.parse(sheet_name)
                for index, row in df.iterrows():
                    strs = []
                    for column_name, column_value in row.items():
                        if column_name is None or column_value is None:
                            continue

                        column_name = str(column_name)
                        column_value = str(column_value)
                        strs.append(f"{column_name.strip()}: {column_value.strip()}")

                    content = "\n".join(strs)
                    try:
                        source = (
                            row[self._source_column]
                            if self._source_column is not None
                            else self._path
                        )
                    except KeyError:
                        raise ValueError(
                            f"Source column '{self._source_column}' not in CSV file."
                        )

                    metadata = {"source": source, "row": index}
                    if self._metadata:
                        metadata.update(self._metadata)  # type: ignore
                    doc = Document(content=content, metadata=metadata)
                    docs.append(doc)

            return docs

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
    def type(cls) -> KnowledgeType:
        """Knowledge type of CSV."""
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        """Return document type."""
        return DocumentType.EXCEL
