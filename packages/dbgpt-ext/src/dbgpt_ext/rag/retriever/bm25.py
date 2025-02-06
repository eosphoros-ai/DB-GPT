"""BM25 retriever."""

import json
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any, List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.retriever.rerank import DefaultRanker, Ranker
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt_app.base import logger


class BM25Retriever(BaseRetriever):
    """BM25 retriever.

    refer https://www.elastic.co/guide/en/elasticsearch/reference/8.9/
    index-modules-similarity.html;
    TF/IDF based similarity that has built-in tf normalization and is supposed to
    work better for short fields (like names). See Okapi_BM25 for more details.
    """

    def __init__(
        self,
        top_k: int = 4,
        es_index: str = "dbgpt",
        es_client: Any = None,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        k1: Optional[float] = 2.0,
        b: Optional[float] = 0.75,
        executor: Optional[Executor] = None,
    ):
        """Create BM25Retriever.

        Args:
            top_k (int): top k
            es_index (str): elasticsearch index
            es_client (Any): elasticsearch client
            query_rewrite (Optional[QueryRewrite]): query rewrite
            rerank (Ranker): rerank
            k1 (Optional[float]): Controls non-linear term frequency normalization
            (saturation). The default value is 2.0.
            b (Optional[float]): Controls to what degree document length normalizes
            tf values. The default value is 0.75.
            executor (Optional[Executor]): executor

        Returns:
            BM25Retriever: BM25 retriever
        """
        super().__init__()
        self._top_k = top_k
        self._query_rewrite = query_rewrite
        try:
            from elasticsearch import Elasticsearch
        except ImportError:
            raise ImportError(
                "please install elasticsearch using `pip install elasticsearch`"
            )
        self._es_client: Elasticsearch = es_client

        self._es_mappings = {
            "properties": {
                "content": {
                    "type": "text",
                    "similarity": "custom_bm25",
                }
            }
        }
        self._es_index_settings = {
            "analysis": {"analyzer": {"default": {"type": "standard"}}},
            "similarity": {
                "custom_bm25": {
                    "type": "BM25",
                    "k1": k1,
                    "b": b,
                }
            },
        }
        self._index_name = es_index
        if not self._es_client.indices.exists(index=self._index_name):
            self._es_client.indices.create(
                index=self._index_name,
                mappings=self._es_mappings,
                settings=self._es_index_settings,
            )
        self._rerank = rerank or DefaultRanker(self._top_k)
        self._executor = executor or ThreadPoolExecutor()

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
        es_query = {"query": {"match": {"content": query}}}
        res = self._es_client.search(index=self._index_name, body=es_query)

        chunks = []
        for r in res["hits"]["hits"]:
            chunks.append(
                Chunk(
                    chunk_id=r["_id"],
                    content=r["_source"]["content"],
                    metadata=json.loads(r["_source"]["metadata"]),
                )
            )
        return chunks[: self._top_k]

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
        es_query = {"query": {"match": {"content": query}}}
        res = self._es_client.search(index=self._index_name, body=es_query)

        chunks_with_scores = []
        for r in res["hits"]["hits"]:
            if r["_score"] >= score_threshold:
                chunks_with_scores.append(
                    Chunk(
                        chunk_id=r["_id"],
                        content=r["_source"]["content"],
                        metadata=json.loads(r["_source"]["metadata"]),
                        score=r["_score"],
                    )
                )
        if score_threshold is not None and len(chunks_with_scores) == 0:
            logger.warning(
                "No relevant docs were retrieved using the relevance score"
                f" threshold {score_threshold}"
            )
        return chunks_with_scores[: self._top_k]

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
        return await blocking_func_to_async(
            self._executor, self.retrieve, query, filters
        )

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
        return await blocking_func_to_async(
            self._executor, self.retrieve, query, filters
        )
