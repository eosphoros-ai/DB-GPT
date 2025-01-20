"""Simple schema linking operator.

Warning: This operator is in development and is not yet ready for production use.
"""

from typing import Any, Optional

from dbgpt.core import LLMClient
from dbgpt.core.awel import MapOperator
from dbgpt.datasource.base import BaseConnector
from dbgpt.storage.base import IndexStoreBase
from dbgpt_ext.rag.schemalinker.schema_linking import SchemaLinking


class SchemaLinkingOperator(MapOperator[Any, Any]):
    """The Schema Linking Operator."""

    def __init__(
        self,
        connector: BaseConnector,
        model_name: str,
        llm: LLMClient,
        top_k: int = 5,
        index_store: Optional[IndexStoreBase] = None,
        **kwargs,
    ):
        """Create the schema linking operator.

        Args:
            connector (BaseConnector): The connection.
            llm (Optional[LLMClient]): base llm
        """
        super().__init__(**kwargs)

        self._schema_linking = SchemaLinking(
            top_k=top_k,
            connector=connector,
            llm=llm,
            model_name=model_name,
            index_store=index_store,
        )

    async def map(self, query: str) -> str:
        """Retrieve the table schemas with llm.

        Args:
            query (str): query.

        Return:
            str: schema information.
        """
        return str(await self._schema_linking.schema_linking_with_llm(query))
