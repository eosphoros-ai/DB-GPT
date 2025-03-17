"""Elasticsearch document store."""

import json
import os
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.storage.base import IndexStoreConfig, logger
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util import string_utils
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt_ext.storage.vector_store.elastic_store import ElasticsearchStoreConfig


class ElasticDocumentStore(FullTextStoreBase):
    """Elasticsearch index store."""

    def __init__(
        self,
        es_config: ElasticsearchStoreConfig,
        name: Optional[str] = "dbgpt",
        k1: Optional[float] = 2.0,
        b: Optional[float] = 0.75,
        executor: Optional[Executor] = None,
    ):
        """Init elasticsearch index store.

        refer https://www.elastic.co/guide/en/elasticsearch/reference/8.9/index-
        modules-similarity.html
        TF/IDF based similarity that has built-in tf normalization and is supposed to
        work better for short fields (like names). See Okapi_BM25 for more details.
        This similarity has the following options:
        """
        super().__init__()
        self._es_config = es_config
        from elasticsearch import Elasticsearch

        self._es_config = es_config
        self._es_url = es_config.uri or os.getenv("ELASTICSEARCH_URL", "localhost")
        self._es_port = es_config.port or os.getenv("ELASTICSEARCH_PORT", "9200")
        self._es_username = es_config.user or os.getenv("ELASTICSEARCH_USER", "elastic")
        self._es_password = es_config.password or os.getenv(
            "ELASTICSEARCH_PASSWORD", "dbgpt"
        )
        self._index_name = name.lower()
        if string_utils.contains_chinese(name):
            bytes_str = name.encode("utf-8")
            hex_str = bytes_str.hex()
            self._index_name = "dbgpt_" + hex_str
        # k1 (Optional[float]): Controls non-linear term frequency normalization
        #             (saturation). The default value is 2.0.
        self._k1 = k1 or 2.0
        # b (Optional[float]): Controls to what degree document length normalizes
        #             tf values. The default value is 0.75.
        self._b = b or 0.75
        if self._es_username and self._es_password:
            self._es_client = Elasticsearch(
                hosts=[f"http://{self._es_url}:{self._es_port}"],
                basic_auth=(self._es_username, self._es_password),
            )
        else:
            self._es_client = Elasticsearch(
                hosts=[f"http://{self._es_url}:{self._es_port}"],
            )
        self._es_index_settings = {
            "analysis": {"analyzer": {"default": {"type": "standard"}}},
            "similarity": {
                "custom_bm25": {
                    "type": "BM25",
                    "k1": self._k1,
                    "b": self._b,
                }
            },
        }
        self._es_mappings = {
            "properties": {
                "content": {
                    "type": "text",
                    "similarity": "custom_bm25",
                },
                "metadata": {
                    "type": "keyword",
                },
            }
        }

        if not self._es_client.indices.exists(index=self._index_name):
            self._es_client.indices.create(
                index=self._index_name,
                mappings=self._es_mappings,
                settings=self._es_index_settings,
            )
        self._executor = executor or ThreadPoolExecutor()

    def get_config(self) -> IndexStoreConfig:
        """Get the es store config."""
        return self._es_config

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in elasticsearch.

        Args:
            chunks(List[Chunk]): document chunks.

        Return:
            List[str]: chunk ids.
        """
        try:
            from elasticsearch.helpers import bulk
        except ImportError:
            raise ValueError("Please install package `pip install elasticsearch`.")
        es_requests = []
        ids = []
        contents = [chunk.content for chunk in chunks]
        metadatas = [json.dumps(chunk.metadata) for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        for i, content in enumerate(contents):
            es_request = {
                "_op_type": "index",
                "_index": self._index_name,
                "content": content,
                "metadata": metadatas[i],
                "_id": chunk_ids[i],
            }
            ids.append(chunk_ids[i])
            es_requests.append(es_request)
        bulk(self._es_client, es_requests)
        self._es_client.indices.refresh(index=self._index_name)
        return ids

    def similar_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Search similar text.

        Args:
            text(str): text.
            topk(int): topk.
            filters(MetadataFilters): filters.

        Return:
            List[Chunk]: similar text.
        """
        es_query = {"query": {"match": {"content": text}}}
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
        return chunks[:topk]

    def similar_search_with_scores(
        self,
        text,
        top_k: int = 10,
        score_threshold: float = 0.3,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search similar text with scores.

        Args:
            text(str): text.
            top_k(int): top k.
            min_score(float): min score.
            filters(MetadataFilters): filters.

        Return:
            List[Tuple[str, float]]: similar text with scores.
        """
        es_query = {"query": {"match": {"content": text}}}
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
        return chunks_with_scores[:top_k]

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Async load document in elasticsearch.

        Args:
            chunks(List[Chunk]): document chunks.
        Return:
            List[str]: chunk ids.
        """
        return await blocking_func_to_async(self._executor, self.load_document, chunks)

    def delete_by_ids(self, ids: str) -> List[str]:
        """Delete document by ids.

        Args:
            ids(List[str]): document ids.
        Return:
            return ids.
        """
        id_list = ids.split(",")
        bulk_body = [
            {"delete": {"_index": self._index_name, "_id": doc_id}}
            for doc_id in id_list
        ]
        self._es_client.bulk(body=bulk_body)
        return id_list

    def delete_vector_name(self, index_name: str):
        """Delete index by name.

        Args:
            index_name(str): The name of index to delete.
        """
        self._es_client.indices.delete(index=self._index_name)
