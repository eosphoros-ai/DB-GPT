"""Embedding retriever operator."""

from functools import reduce
from typing import List, Optional, Union

from dbgpt.core import Chunk
from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.rag.retriever.embedding import EmbeddingRetriever
from dbgpt.rag.retriever.rerank import Ranker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.storage.vector_store.connector import VectorStoreConnector


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
