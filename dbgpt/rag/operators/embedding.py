"""Embedding retriever operator."""

from functools import reduce
from typing import List, Optional, Union

from dbgpt.core import Chunk
from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.storage.vector_store.connector import VectorStoreConnector

from ..assembler.embedding import EmbeddingAssembler
from ..chunk_manager import ChunkParameters
from ..knowledge import Knowledge
from ..retriever.embedding import EmbeddingRetriever
from ..retriever.rerank import Ranker
from ..retriever.rewrite import QueryRewrite
from .assembler import AssemblerOperator


class EmbeddingRetrieverOperator(RetrieverOperator[Union[str, List[str]], List[Chunk]]):
    """The Embedding Retriever Operator."""

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        top_k: int,
        score_threshold: float = 0.3,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        **kwargs
    ):
        """Create a new EmbeddingRetrieverOperator."""
        super().__init__(**kwargs)
        self._score_threshold = score_threshold
        self._retriever = EmbeddingRetriever(
            vector_store_connector=vector_store_connector,
            top_k=top_k,
            query_rewrite=query_rewrite,
            rerank=rerank,
        )

    def retrieve(self, query: Union[str, List[str]]) -> List[Chunk]:
        """Retrieve the candidates."""
        if isinstance(query, str):
            return self._retriever.retrieve_with_scores(query, self._score_threshold)
        elif isinstance(query, list):
            candidates = [
                self._retriever.retrieve_with_scores(q, self._score_threshold)
                for q in query
            ]
            return reduce(lambda x, y: x + y, candidates)


class EmbeddingAssemblerOperator(AssemblerOperator[Knowledge, List[Chunk]]):
    """The Embedding Assembler Operator."""

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        chunk_parameters: Optional[ChunkParameters] = ChunkParameters(
            chunk_strategy="CHUNK_BY_SIZE"
        ),
        **kwargs
    ):
        """Create a new EmbeddingAssemblerOperator.

        Args:
            vector_store_connector (VectorStoreConnector): The vector store connector.
            chunk_parameters (Optional[ChunkParameters], optional): The chunk
                parameters. Defaults to ChunkParameters(chunk_strategy="CHUNK_BY_SIZE").
        """
        self._chunk_parameters = chunk_parameters
        self._vector_store_connector = vector_store_connector
        super().__init__(**kwargs)

    def assemble(self, knowledge: Knowledge) -> List[Chunk]:
        """Assemble knowledge for input value."""
        assembler = EmbeddingAssembler.load_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=self._chunk_parameters,
            vector_store_connector=self._vector_store_connector,
        )
        assembler.persist()
        return assembler.get_chunks()
