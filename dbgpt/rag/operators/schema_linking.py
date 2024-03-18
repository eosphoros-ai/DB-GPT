"""Simple schema linking operator.

Warning: This operator is in development and is not yet ready for production use.
"""

from typing import Any, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.datasource.rdbms.base import RDBMSConnector
from dbgpt.rag.schemalinker.schema_linking import SchemaLinking
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class SchemaLinkingOperator(MapOperator[Any, Any]):
    """The Schema Linking Operator."""

    def __init__(
        self,
        connection: RDBMSConnector,
        model_name: str,
        llm: LLMClient,
        top_k: int = 5,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs
    ):
        """Create the schema linking operator.

        Args:
            connection (RDBMSConnector): The connection.
            llm (Optional[LLMClient]): base llm
        """
        super().__init__(**kwargs)

        self._schema_linking = SchemaLinking(
            top_k=top_k,
            connection=connection,
            llm=llm,
            model_name=model_name,
            vector_store_connector=vector_store_connector,
        )

    async def map(self, query: str) -> str:
        """Retrieve the table schemas with llm.

        Args:
            query (str): query.

        Return:
            str: schema information.
        """
        return str(await self._schema_linking.schema_linking_with_llm(query))
