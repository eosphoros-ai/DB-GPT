from typing import Any, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.rag.schemalinker.schema_linking import SchemaLinking


class SchemaLinkingOperator(MapOperator[Any, Any]):
    """The Schema Linking Operator."""

    def __init__(
        self,
        connection: Optional[RDBMSDatabase] = None,
        llm: Optional[LLMClient] = None,
        **kwargs
    ):
        """Init the schema linking operator
        Args:
            connection (RDBMSDatabase): The connection.
            llm (Optional[LLMClient]): base llm
        """
        super().__init__(**kwargs)
        self._schema_linking = SchemaLinking(
            connection=connection,
            llm=llm,
        )

    async def map(self, query: str) -> str:
        """retrieve table schemas.
        Args:
            query (str): query.
        Return:
            str: schema info
        """
        return await self._schema_linking.schema_linking(query)
