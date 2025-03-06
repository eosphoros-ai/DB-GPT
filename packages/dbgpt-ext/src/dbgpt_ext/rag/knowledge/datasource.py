"""Datasource Knowledge."""

from typing import Any, Dict, List, Optional, Union

from dbgpt.core import Document
from dbgpt.datasource import BaseConnector
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)

from ..summary.rdbms_db_summary import (
    _DEFAULT_COLUMN_SEPARATOR,
    _DEFAULT_SUMMARY_TEMPLATE,
    _parse_db_summary_with_metadata,
)


class DatasourceKnowledge(Knowledge):
    """Datasource Knowledge."""

    def __init__(
        self,
        connector: BaseConnector,
        summary_template: str = _DEFAULT_SUMMARY_TEMPLATE,
        separator: str = "--table-field-separator--",
        column_separator: str = _DEFAULT_COLUMN_SEPARATOR,
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        model_dimension: int = 512,
        **kwargs: Any,
    ) -> None:
        """Create Datasource Knowledge with Knowledge arguments.

        Args:
            connector(BaseConnector): connector
            summary_template(str, optional): summary template
            separator(str, optional): separator used to separate
                table's basic info and fields.
                defaults `-- table-field-separator--`
            knowledge_type(KnowledgeType, optional): knowledge type
            metadata(Dict[str, Union[str, List[str]], optional): metadata
            model_dimension(int, optional): The threshold for splitting field string
        """
        self._separator = separator
        self._column_separator = column_separator
        self._connector = connector
        self._summary_template = summary_template
        self._model_dimension = model_dimension
        super().__init__(knowledge_type=knowledge_type, metadata=metadata, **kwargs)

    def _load(self) -> List[Document]:
        """Load datasource document from data_loader."""
        docs = []
        db_summary_with_metadata = _parse_db_summary_with_metadata(
            self._connector,
            self._summary_template,
            self._separator,
            column_separator=self._column_separator,
            model_dimension=self._model_dimension,
        )
        for summary, table_metadata in db_summary_with_metadata:
            metadata = {"source": "database"}

            if self._metadata:
                metadata.update(self._metadata)  # type: ignore
            table_metadata.update(metadata)
            docs.append(Document(content=summary, metadata=table_metadata))
        return docs

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return support chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
            ChunkStrategy.CHUNK_BY_PAGE,
        ]

    @classmethod
    def type(cls) -> KnowledgeType:
        """Knowledge type of Datasource."""
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        """Return document type."""
        return DocumentType.DATASOURCE

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy.

        Returns:
            ChunkStrategy: default chunk strategy
        """
        return ChunkStrategy.CHUNK_BY_PAGE
