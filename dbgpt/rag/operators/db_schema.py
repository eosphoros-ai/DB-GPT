"""The DBSchema Retriever Operator."""

from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.datasource.base import BaseConnector
from dbgpt.storage.vector_store.connector import VectorStoreConnector

from ..assembler.db_schema import DBSchemaAssembler
from ..retriever.db_schema import DBSchemaRetriever
from .assembler import AssemblerOperator


class DBSchemaRetrieverOperator(RetrieverOperator[str, List[Chunk]]):
    """The DBSchema Retriever Operator.

    Args:
        connector (BaseConnector): The connection.
        top_k (int, optional): The top k. Defaults to 4.
        vector_store_connector (VectorStoreConnector, optional): The vector store
        connector. Defaults to None.
    """

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        top_k: int = 4,
        connector: Optional[BaseConnector] = None,
        **kwargs
    ):
        """Create a new DBSchemaRetrieverOperator."""
        super().__init__(**kwargs)
        self._retriever = DBSchemaRetriever(
            top_k=top_k,
            connector=connector,
            vector_store_connector=vector_store_connector,
        )

    def retrieve(self, query: str) -> List[Chunk]:
        """Retrieve the table schemas.

        Args:
            query (str): The query.
        """
        return self._retriever.retrieve(query)


class DBSchemaAssemblerOperator(AssemblerOperator[BaseConnector, List[Chunk]]):
    """The DBSchema Assembler Operator."""

    def __init__(
        self,
        connector: BaseConnector,
        vector_store_connector: VectorStoreConnector,
        **kwargs
    ):
        """Create a new DBSchemaAssemblerOperator.

        Args:
            connector (BaseConnector): The connection.
            vector_store_connector (VectorStoreConnector): The vector store connector.
        """
        self._vector_store_connector = vector_store_connector
        self._connector = connector
        super().__init__(**kwargs)

    def assemble(self, dummy_value) -> List[Chunk]:
        """Persist the database schema.

        Args:
            dummy_value: Dummy value, not used.

        Returns:
            List[Chunk]: The chunks.
        """
        assembler = DBSchemaAssembler.load_from_connection(
            connector=self._connector,
            vector_store_connector=self._vector_store_connector,
        )
        assembler.persist()
        return assembler.get_chunks()
