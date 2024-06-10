"""The DBSchema Retriever Operator."""

from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.datasource.base import BaseConnector

from ..assembler.db_schema import DBSchemaAssembler
from ..chunk_manager import ChunkParameters
from ..index.base import IndexStoreBase
from ..retriever.db_schema import DBSchemaRetriever
from .assembler import AssemblerOperator


class DBSchemaRetrieverOperator(RetrieverOperator[str, List[Chunk]]):
    """The DBSchema Retriever Operator.

    Args:
        connector (BaseConnector): The connection.
        top_k (int, optional): The top k. Defaults to 4.
        index_store (IndexStoreBase, optional): The vector store
        connector. Defaults to None.
    """

    def __init__(
        self,
        index_store: IndexStoreBase,
        top_k: int = 4,
        connector: Optional[BaseConnector] = None,
        **kwargs
    ):
        """Create a new DBSchemaRetrieverOperator."""
        super().__init__(**kwargs)
        self._retriever = DBSchemaRetriever(
            top_k=top_k,
            connector=connector,
            index_store=index_store,
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
        index_store: IndexStoreBase,
        chunk_parameters: Optional[ChunkParameters] = None,
        **kwargs
    ):
        """Create a new DBSchemaAssemblerOperator.

        Args:
            connector (BaseConnector): The connection.
            index_store (IndexStoreBase): The Storage IndexStoreBase.
            chunk_parameters (Optional[ChunkParameters], optional): The chunk
                parameters.
        """
        if not chunk_parameters:
            chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
        self._chunk_parameters = chunk_parameters
        self._index_store = index_store
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
            chunk_parameters=self._chunk_parameters,
            index_store=self._index_store,
        )
        assembler.persist()
        return assembler.get_chunks()
