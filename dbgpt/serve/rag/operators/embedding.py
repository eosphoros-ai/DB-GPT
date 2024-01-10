from typing import Any, Optional

from dbgpt.core.awel.task.base import IN
from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.serve.rag.assembler.embedding import EmbeddingAssembler
from dbgpt.serve.rag.operators.base import AssemblerOperator
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class EmbeddingAssemblerOperator(AssemblerOperator[Any, Any]):
    """The Embedding Assembler Operator.
    Args:
        knowledge (Knowledge): The knowledge.
        chunk_parameters (Optional[ChunkParameters], optional): The chunk parameters. Defaults to None.
        vector_store_connector (VectorStoreConnector, optional): The vector store connector. Defaults to None.
    """

    def __init__(
        self,
        chunk_parameters: Optional[ChunkParameters] = ChunkParameters(
            chunk_strategy="CHUNK_BY_SIZE"
        ),
        vector_store_connector: VectorStoreConnector = None,
        **kwargs
    ):
        """
        Args:
            chunk_parameters (Optional[ChunkParameters], optional): The chunk parameters. Defaults to ChunkParameters(chunk_strategy="CHUNK_BY_SIZE").
            vector_store_connector (VectorStoreConnector, optional): The vector store connector. Defaults to None.
        """
        self._chunk_parameters = chunk_parameters
        self._vector_store_connector = vector_store_connector
        super().__init__(**kwargs)

    def assemble(self, knowledge: IN) -> Any:
        """assemble knowledge for input value."""
        assembler = EmbeddingAssembler.load_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=self._chunk_parameters,
            vector_store_connector=self._vector_store_connector,
        )
        assembler.persist()
        return assembler.get_chunks()
