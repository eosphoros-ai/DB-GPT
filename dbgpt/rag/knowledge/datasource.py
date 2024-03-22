"""Datasource Knowledge."""
from typing import Any, List, Optional

from dbgpt.core import Document
from dbgpt.datasource import BaseConnector

from ..summary.rdbms_db_summary import _parse_db_summary
from .base import ChunkStrategy, DocumentType, Knowledge, KnowledgeType


class DatasourceKnowledge(Knowledge):
    """Datasource Knowledge."""

    def __init__(
        self,
        connector: BaseConnector,
        summary_template: str = "{table_name}({columns})",
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
        **kwargs: Any,
    ) -> None:
        """Create Datasource Knowledge with Knowledge arguments.

        Args:
            path(str,  optional): file path
            knowledge_type(KnowledgeType, optional): knowledge type
            data_loader(Any, optional): loader
        """
        self._connector = connector
        self._summary_template = summary_template
        super().__init__(knowledge_type=knowledge_type, **kwargs)

    def _load(self) -> List[Document]:
        """Load datasource document from data_loader."""
        docs = []
        for table_summary in _parse_db_summary(self._connector, self._summary_template):
            docs.append(
                Document(content=table_summary, metadata={"source": "database"})
            )
        return docs

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return support chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def type(cls) -> KnowledgeType:
        """Knowledge type of Datasource."""
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        """Return document type."""
        return DocumentType.DATASOURCE
