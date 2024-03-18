"""Datasource operator for RDBMS database."""

from typing import Any

from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.rag.summary.rdbms_db_summary import _parse_db_summary


class DatasourceRetrieverOperator(RetrieverOperator[Any, Any]):
    """The Datasource Retriever Operator."""

    def __init__(self, connection: RDBMSConnector, **kwargs):
        """Create a new DatasourceRetrieverOperator."""
        super().__init__(**kwargs)
        self._connection = connection

    def retrieve(self, input_value: Any) -> Any:
        """Retrieve the database summary."""
        summary = _parse_db_summary(self._connection)
        return summary
