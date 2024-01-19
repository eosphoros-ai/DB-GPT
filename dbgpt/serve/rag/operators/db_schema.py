from typing import Any, Optional

from dbgpt.core.awel.task.base import IN
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.serve.rag.assembler.db_schema import DBSchemaAssembler
from dbgpt.serve.rag.operators.base import AssemblerOperator
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class DBSchemaAssemblerOperator(AssemblerOperator[Any, Any]):
    """The DBSchema Assembler Operator.
    Args:
        connection (RDBMSDatabase): The connection.
        chunk_parameters (Optional[ChunkParameters], optional): The chunk parameters. Defaults to None.
        vector_store_connector (VectorStoreConnector, optional): The vector store connector. Defaults to None.
    """

    def __init__(
        self,
        connection: RDBMSDatabase = None,
        vector_store_connector: Optional[VectorStoreConnector] = None,
        **kwargs
    ):
        self._connection = connection
        self._vector_store_connector = vector_store_connector
        self._assembler = DBSchemaAssembler.load_from_connection(
            connection=self._connection,
            vector_store_connector=self._vector_store_connector,
        )
        super().__init__(**kwargs)

    def assemble(self, input_value: IN) -> Any:
        """assemble knowledge for input value."""
        if self._vector_store_connector:
            self._assembler.persist()
        return self._assembler.get_chunks()
