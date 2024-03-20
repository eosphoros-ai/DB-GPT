"""The DBSchema Retriever Operator."""

from typing import Any, Optional

from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.rag.retriever.db_schema import DBSchemaRetriever
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class DBSchemaRetrieverOperator(RetrieverOperator[Any, Any]):
    """The DBSchema Retriever Operator.

    Args:
        connection (RDBMSConnector): The connection.
        top_k (int, optional): The top k. Defaults to 4.
        vector_store_connector (VectorStoreConnector, optional): The vector store
        connector. Defaults to None.
    """

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        top_k: int = 4,
        connection: Optional[RDBMSConnector] = None,
        **kwargs
    ):
        """Create a new DBSchemaRetrieverOperator."""
        super().__init__(**kwargs)
        self._retriever = DBSchemaRetriever(
            top_k=top_k,
            connection=connection,
            vector_store_connector=vector_store_connector,
        )

    def retrieve(self, query: Any) -> Any:
        """Retrieve the table schemas.

        Args:
            query (IN): query.
        """
        return self._retriever.retrieve(query)
