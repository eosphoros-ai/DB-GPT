"""Embedding retriever."""
from functools import reduce
from typing import List, Optional, cast

from dbgpt.core import Chunk
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.retriever.rerank import DefaultRanker, Ranker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.chat_util import run_async_tasks
from dbgpt.util.tracer import root_tracer


class EmbeddingRetriever(BaseRetriever):
    """Embedding retriever."""

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        top_k: int = 4,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
    ):
        """Create EmbeddingRetriever.

        Args:
            top_k (int): top k
            query_rewrite (Optional[QueryRewrite]): query rewrite
            rerank (Ranker): rerank
            vector_store_connector (VectorStoreConnector): vector store connector

        Examples:
            .. code-block:: python

                from dbgpt.storage.vector_store.connector import VectorStoreConnector
                from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig
                from dbgpt.rag.retriever.embedding import EmbeddingRetriever
                from dbgpt.rag.embedding.embedding_factory import (
                    DefaultEmbeddingFactory,
                )

                embedding_factory = DefaultEmbeddingFactory()
                from dbgpt.rag.retriever.embedding import EmbeddingRetriever
                from dbgpt.storage.vector_store.connector import VectorStoreConnector

                embedding_fn = embedding_factory.create(
                    model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
                )
                vector_name = "test"
                config = ChromaVectorConfig(name=vector_name, embedding_fn=embedding_fn)
                vector_store_connector = VectorStoreConnector(
                    vector_store_type="Chroma",
                    vector_store_config=config,
                )
                embedding_retriever = EmbeddingRetriever(
                    top_k=3, vector_store_connector=vector_store_connector
                )
                chunks = embedding_retriever.retrieve("your query text")
                print(
                    f"embedding retriever results:{[chunk.content for chunk in chunks]}"
                )
        """
        self._top_k = top_k
        self._query_rewrite = query_rewrite
        self._vector_store_connector = vector_store_connector
        self._rerank = rerank or DefaultRanker(self._top_k)

    def _retrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text

        Return:
            List[Chunk]: list of chunks
        """
        queries = [query]
        candidates = [
            self._vector_store_connector.similar_search(query, self._top_k)
            for query in queries
        ]
        res_candidates = cast(List[Chunk], reduce(lambda x, y: x + y, candidates))
        return res_candidates

    def _retrieve_with_score(self, query: str, score_threshold: float) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold

        Return:
            List[Chunk]: list of chunks with score
        """
        queries = [query]
        candidates_with_score = [
            self._vector_store_connector.similar_search_with_scores(
                query, self._top_k, score_threshold
            )
            for query in queries
        ]
        new_candidates_with_score = cast(
            List[Chunk], reduce(lambda x, y: x + y, candidates_with_score)
        )
        new_candidates_with_score = self._rerank.rank(new_candidates_with_score)
        return new_candidates_with_score

    async def _aretrieve(self, query: str) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text

        Return:
            List[Chunk]: list of chunks
        """
        queries = [query]
        if self._query_rewrite:
            candidates_tasks = [self._similarity_search(query) for query in queries]
            chunks = await self._run_async_tasks(candidates_tasks)
            context = "\n".join([chunk.content for chunk in chunks])
            new_queries = await self._query_rewrite.rewrite(
                origin_query=query, context=context, nums=1
            )
            queries.extend(new_queries)
        candidates = [self._similarity_search(query) for query in queries]
        new_candidates = await run_async_tasks(tasks=candidates, concurrency_limit=1)
        return new_candidates

    async def _aretrieve_with_score(
        self, query: str, score_threshold: float
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold

        Return:
            List[Chunk]: list of chunks with score
        """
        queries = [query]
        if self._query_rewrite:
            with root_tracer.start_span(
                "EmbeddingRetriever.query_rewrite.similarity_search",
                metadata={"query": query, "score_threshold": score_threshold},
            ):
                candidates_tasks = [self._similarity_search(query) for query in queries]
                chunks = await self._run_async_tasks(candidates_tasks)
                context = "\n".join([chunk.content for chunk in chunks])
            with root_tracer.start_span(
                "EmbeddingRetriever.query_rewrite.rewrite",
                metadata={"query": query, "context": context, "nums": 1},
            ):
                new_queries = await self._query_rewrite.rewrite(
                    origin_query=query, context=context, nums=1
                )
                queries.extend(new_queries)

        with root_tracer.start_span(
            "EmbeddingRetriever.similarity_search_with_score",
            metadata={"query": query, "score_threshold": score_threshold},
        ):
            candidates_with_score = [
                self._similarity_search_with_score(query, score_threshold)
                for query in queries
            ]
            res_candidates_with_score = await run_async_tasks(
                tasks=candidates_with_score, concurrency_limit=1
            )
            new_candidates_with_score = cast(
                List[Chunk], reduce(lambda x, y: x + y, res_candidates_with_score)
            )

        with root_tracer.start_span(
            "EmbeddingRetriever.rerank",
            metadata={
                "query": query,
                "score_threshold": score_threshold,
                "rerank_cls": self._rerank.__class__.__name__,
            },
        ):
            new_candidates_with_score = self._rerank.rank(new_candidates_with_score)
            return new_candidates_with_score

    async def _similarity_search(self, query) -> List[Chunk]:
        """Similar search."""
        return self._vector_store_connector.similar_search(
            query,
            self._top_k,
        )

    async def _run_async_tasks(self, tasks) -> List[Chunk]:
        """Run async tasks."""
        candidates = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        candidates = reduce(lambda x, y: x + y, candidates)
        return cast(List[Chunk], candidates)

    async def _similarity_search_with_score(
        self, query, score_threshold
    ) -> List[Chunk]:
        """Similar search with score."""
        return self._vector_store_connector.similar_search_with_scores(
            query, self._top_k, score_threshold
        )
