"""Datasource Knowledge."""
from typing import Any, Dict, List, Optional, Union

from dbgpt.core import Document
from dbgpt.datasource import BaseConnector

from ..summary.gdbms_db_summary import _parse_db_summary as _parse_gdb_summary
from ..summary.rdbms_db_summary import _parse_db_summary
from .base import ChunkStrategy, DocumentType, Knowledge, KnowledgeType


class DatasourceKnowledge(Knowledge):
    """Datasource Knowledge."""

    def __init__(
        self,
        connector: BaseConnector,
        summary_template: str = "{table_name}({columns})",
        knowledge_type: Optional[KnowledgeType] = KnowledgeType.DOCUMENT,
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        **kwargs: Any,
    ) -> None:
        """Create Datasource Knowledge with Knowledge arguments.

        Args:
            connector(BaseConnector): connector
            summary_template(str, optional): summary template
            knowledge_type(KnowledgeType, optional): knowledge type
            metadata(Dict[str, Union[str, List[str]], optional): metadata
        """
        self._connector = connector
        self._summary_template = summary_template
        super().__init__(knowledge_type=knowledge_type, metadata=metadata, **kwargs)

    def _load(self) -> List[Document]:
        """Load datasource document from data_loader."""
        docs = []
        if self._connector.is_graph_type():
            db_summary = _parse_gdb_summary(self._connector, self._summary_template)
        else:
            db_summary = _parse_db_summary(self._connector, self._summary_template)
        for table_summary in db_summary:
            metadata = {"source": "database"}
            if self._metadata:
                metadata.update(self._metadata)  # type: ignore
            docs.append(Document(content=table_summary, metadata=metadata))
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
