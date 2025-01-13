"""Embedding retriever."""

from functools import reduce
from typing import Any, Dict, List, Optional, cast

from dbgpt.core import Chunk
from dbgpt.rag.index.base import IndexStoreBase
from dbgpt.rag.retriever.base import BaseRetriever, RetrieverStrategy
from dbgpt.rag.retriever.rerank import DefaultRanker, Ranker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.chat_util import run_async_tasks
from dbgpt.util.tracer import root_tracer


class EmbeddingRetriever(BaseRetriever):
    """Embedding retriever."""

    def __init__(
        self,
        index_store: IndexStoreBase,
        top_k: int = 4,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        retrieve_strategy: Optional[RetrieverStrategy] = RetrieverStrategy.EMBEDDING,
    ):
        """Create EmbeddingRetriever.

        Args:
            index_store(IndexStore): vector store connector
            top_k (int): top k
            query_rewrite (Optional[QueryRewrite]): query rewrite
            rerank (Ranker): rerank

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
        self._index_store = index_store
        self._rerank = rerank or DefaultRanker(self._top_k)
        self._retrieve_strategy = retrieve_strategy

    def load_document(self, chunks: List[Chunk], **kwargs: Dict[str, Any]) -> List[str]:
        """Load document in vector database.

        Args:
            chunks (List[Chunk]): document chunks.
        Return:
            List[str]: chunk ids.
        """
        return self._index_store.load_document(chunks)

    def _retrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        queries = [query]
        candidates = [
            self._index_store.similar_search(query, self._top_k, filters)
            for query in queries
        ]
        res_candidates = cast(List[Chunk], reduce(lambda x, y: x + y, candidates))
        return res_candidates

    def _retrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks with score
        """
        queries = [query]
        candidates_with_score = [
            self._index_store.similar_search_with_scores(
                query, self._top_k, score_threshold, filters
            )
            for query in queries
        ]
        new_candidates_with_score = cast(
            List[Chunk], reduce(lambda x, y: x + y, candidates_with_score)
        )
        new_candidates_with_score = self._rerank.rank(new_candidates_with_score, query)
        return new_candidates_with_score

    async def _aretrieve(
        self, query: str, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Retrieve knowledge chunks.

        Args:
            query (str): query text.
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        queries = [query]
        if self._query_rewrite:
            candidates_tasks = [
                self._similarity_search(
                    query, filters, root_tracer.get_current_span_id()
                )
                for query in queries
            ]
            chunks = await self._run_async_tasks(candidates_tasks)
            context = "\n".join([chunk.content for chunk in chunks])
            new_queries = await self._query_rewrite.rewrite(
                origin_query=query, context=context, nums=1
            )
            queries.extend(new_queries)
        candidates = [
            self._similarity_search(query, filters, root_tracer.get_current_span_id())
            for query in queries
        ]
        new_candidates = await run_async_tasks(tasks=candidates, concurrency_limit=1)
        return new_candidates

    async def _aretrieve_with_score(
        self,
        query: str,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve knowledge chunks with score.

        Args:
            query (str): query text
            score_threshold (float): score threshold
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks with score
        """
        queries = [query]
        if self._query_rewrite:
            with root_tracer.start_span(
                "dbgpt.rag.retriever.embeddings.query_rewrite.similarity_search",
                metadata={"query": query, "score_threshold": score_threshold},
            ):
                candidates_tasks = [
                    self._similarity_search(
                        query, filters, root_tracer.get_current_span_id()
                    )
                    for query in queries
                ]
                chunks = await self._run_async_tasks(candidates_tasks)
                context = "\n".join([chunk.content for chunk in chunks])
            with root_tracer.start_span(
                "dbgpt.rag.retriever.embeddings.query_rewrite.rewrite",
                metadata={"query": query, "context": context, "nums": 1},
            ):
                new_queries = await self._query_rewrite.rewrite(
                    origin_query=query, context=context, nums=1
                )
                queries.extend(new_queries)

        with root_tracer.start_span(
            "dbgpt.rag.retriever.embeddings.similarity_search_with_score",
            metadata={"query": query, "score_threshold": score_threshold},
        ):
            candidates_with_score = [
                self._similarity_search_with_score(
                    query, score_threshold, filters, root_tracer.get_current_span_id()
                )
                for query in queries
            ]
            res_candidates_with_score = await run_async_tasks(
                tasks=candidates_with_score, concurrency_limit=1
            )
            new_candidates_with_score = cast(
                List[Chunk], reduce(lambda x, y: x + y, res_candidates_with_score)
            )

        with root_tracer.start_span(
            "dbgpt.rag.retriever.embeddings.rerank",
            metadata={
                "query": query,
                "score_threshold": score_threshold,
                "rerank_cls": self._rerank.__class__.__name__,
            },
        ):
            new_candidates_with_score = await self._rerank.arank(
                new_candidates_with_score, query
            )
            return new_candidates_with_score

    async def _similarity_search(
        self,
        query,
        filters: Optional[MetadataFilters] = None,
        parent_span_id: Optional[str] = None,
    ) -> List[Chunk]:
        """Similar search."""
        with root_tracer.start_span(
            "dbgpt.rag.retriever.embeddings.similarity_search",
            parent_span_id,
            metadata={
                "query": query,
            },
        ):
            return await self._index_store.asimilar_search(query, self._top_k, filters)

    async def _run_async_tasks(self, tasks) -> List[Chunk]:
        """Run async tasks."""
        candidates = await run_async_tasks(tasks=tasks, concurrency_limit=1)
        candidates = reduce(lambda x, y: x + y, candidates)
        return cast(List[Chunk], candidates)

    async def _similarity_search_with_score(
        self,
        query,
        score_threshold,
        filters: Optional[MetadataFilters] = None,
        parent_span_id: Optional[str] = None,
    ) -> List[Chunk]:
        """Similar search with score."""
        with root_tracer.start_span(
            "dbgpt.rag.retriever.embeddings._do_similarity_search_with_score",
            parent_span_id,
            metadata={
                "query": query,
                "score_threshold": score_threshold,
            },
        ):
            return await self._index_store.asimilar_search_with_scores(
                query, self._top_k, score_threshold, filters
            )

    @classmethod
    def name(cls):
        """Return retriever name."""
        return "embedding_retriever"
