from functools import reduce
from typing import Any, Optional

from dbgpt.core.awel.task.base import IN
from dbgpt.core.interface.operator.retriever import RetrieverOperator
from dbgpt.rag.retriever.embedding import EmbeddingRetriever
from dbgpt.rag.retriever.rerank import Ranker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.storage.vector_store.connector import VectorStoreConnector


class EmbeddingRetrieverOperator(RetrieverOperator[Any, Any]):
    def __init__(
        self,
        top_k: int,
        score_threshold: Optional[float] = 0.3,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Ranker = None,
        vector_store_connector: VectorStoreConnector = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._score_threshold = score_threshold
        self._retriever = EmbeddingRetriever(
            top_k=top_k,
            query_rewrite=query_rewrite,
            rerank=rerank,
            vector_store_connector=vector_store_connector,
        )

    def retrieve(self, query: IN) -> Any:
        if isinstance(query, str):
            return self._retriever.retrieve_with_scores(query, self._score_threshold)
        elif isinstance(query, list):
            candidates = [
                self._retriever.retrieve_with_scores(q, self._score_threshold)
                for q in query
            ]
            return reduce(lambda x, y: x + y, candidates)
