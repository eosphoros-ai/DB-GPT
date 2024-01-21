from typing import Any, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.rag.schemalinker.schema_linking import SchemaLinking
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class SchemaLinkingOperator(MapOperator[Any, Any]):
    """The Schema Linking Operator."""

    def __init__(
        self,
        top_k: int = 5,
        connection: Optional[RDBMSDatabase] = None,
        llm: Optional[LLMClient] = None,
        model_name: Optional[str] = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs
    ):
        """Init the schema linking operator
        Args:
            connection (RDBMSDatabase): The connection.
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
        """retrieve table schemas.
        Args:
            query (str): query.
        Return:
            str: schema info
        """
        return str(await self._schema_linking.schema_linking_with_llm(query))
