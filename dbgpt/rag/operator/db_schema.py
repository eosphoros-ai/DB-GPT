from typing import Any, Optional

from dbgpt.core.awel.task.base import IN
from dbgpt.core.interface.retriever import RetrieverOperator
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.rag.retriever.db_schema import DBSchemaRetriever
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class DBSchemaRetrieverOperator(RetrieverOperator[Any, Any]):
    """The DBSchema Retriever Operator.
    Args:
        connection (RDBMSDatabase): The connection.
        top_k (int, optional): The top k. Defaults to 4.
        vector_store_connector (VectorStoreConnector, optional): The vector store connector. Defaults to None.
    """

    def __init__(
        self,
        top_k: int = 4,
        connection: Optional[RDBMSDatabase] = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._retriever = DBSchemaRetriever(
            top_k=top_k,
            connection=connection,
            vector_store_connector=vector_store_connector,
        )

    def retrieve(self, query: IN) -> Any:
        """retrieve table schemas.
        Args:
            query (IN): query.
        """
        return self._retriever.retrieve(query)
