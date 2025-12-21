"""Elasticsearch document store."""

import json
import os
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.storage.base import IndexStoreConfig, logger
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.storage.vector_store.filters import (
    FilterCondition,
    FilterOperator,
    MetadataFilters,
)
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
                    # Use object so metadata fields stay queryable for filters
                    "type": "object",
                    "dynamic": True,
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

    def is_support_full_text_search(self) -> bool:
        # 重写，避免继承父类的默认实现
        """Support full text search.

           Elasticsearch supports full text search.

        Return:
            bool: True if full text search is supported.
        """
        return True  # Elasticsearch 支持全文检索

    def full_text_search(
        self, text: str, topk: int, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        # 重写，使用现有的 similar_search_with_scores 方法实现全文检索
        """Full text search in Elasticsearch.

        Args:
            text (str): The query text.
            topk (int): Number of results to return. Default is 10.

        Returns:
            List[Chunk]: Search results as chunks.
        """
        score_threshold = 0.0
        return self.similar_search_with_scores(
            text=text, top_k=topk, score_threshold=score_threshold, filters=filters
        )

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
        metadatas = [self._normalize_metadata(chunk.metadata) for chunk in chunks]
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
        es_query = self._build_query(text, filters)
        res = self._es_client.search(
            index=self._index_name, body=es_query, size=topk, track_total_hits=False
        )

        chunks = []
        for r in res["hits"]["hits"]:
            metadata = self._normalize_metadata(r["_source"].get("metadata"))
            chunks.append(
                Chunk(
                    chunk_id=r["_id"],
                    content=r["_source"]["content"],
                    metadata=metadata,
                )
            )
        return chunks

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
        es_query = self._build_query(text, filters)
        res = self._es_client.search(
            index=self._index_name, body=es_query, size=top_k, track_total_hits=False
        )

        chunks_with_scores = []
        for r in res["hits"]["hits"]:
            if r["_score"] >= score_threshold:
                metadata = self._normalize_metadata(r["_source"].get("metadata"))
                chunks_with_scores.append(
                    Chunk(
                        chunk_id=r["_id"],
                        content=r["_source"]["content"],
                        metadata=metadata,
                        score=r["_score"],
                    )
                )
        if score_threshold is not None and len(chunks_with_scores) == 0:
            logger.warning(
                "No relevant docs were retrieved using the relevance score"
                f" threshold {score_threshold}"
            )
        return chunks_with_scores[:top_k]

    async def aload_document(
        self, chunks: List[Chunk], file_id: Optional[str] = None
    ) -> List[str]:
        """Async load document in elasticsearch.

        Args:
            chunks(List[Chunk]): document chunks.
        Return:
            List[str]: chunk ids.
        """
        # 新增修改：将 file_id 注入到每个 chunk 的元数据中
        if file_id:
            # 确保 metadata 字段存在，然后添加或更新 file_id
            for chunk in chunks:
                if not hasattr(chunk, "metadata"):
                    chunk.metadata = {}
                chunk.metadata["file_id"] = file_id
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

    def _build_query(self, text: str, filters: Optional[MetadataFilters]):
        must_clauses = [{"match": {"content": text}}]
        filter_clause = self._build_metadata_filter(filters)
        if filter_clause:
            must_clauses.append(filter_clause)
        return {"query": {"bool": {"must": must_clauses}}}

    def _build_metadata_filter(self, filters: Optional[MetadataFilters]):
        """Translate MetadataFilters to elasticsearch bool clause."""
        if not filters or not filters.filters:
            return None

        clauses = []
        for f in filters.filters:
            field_name = f"metadata.{f.key}"
            if f.operator == FilterOperator.EQ:
                clauses.append({"term": {field_name: f.value}})
            elif f.operator == FilterOperator.IN:
                values = f.value if isinstance(f.value, list) else [f.value]
                clauses.append({"terms": {field_name: values}})
            elif f.operator == FilterOperator.NE:
                clauses.append({"bool": {"must_not": {"term": {field_name: f.value}}}})
            else:
                logger.warning(
                    "Unsupported filter operator %s for elastic full text search",
                    f.operator,
                )
        if not clauses:
            return None
        if filters.condition == FilterCondition.OR:
            return {"bool": {"should": clauses, "minimum_should_match": 1}}
        return {"bool": {"must": clauses}}

    def _normalize_metadata(self, metadata):
        """Ensure metadata is stored as a dict for downstream consumers."""
        if metadata is None:
            return {}
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            try:
                return json.loads(metadata)
            except Exception:
                # Fallback to wrapping the raw string to avoid breaking callers
                return {"value": metadata}
        try:
            return dict(metadata)
        except Exception:
            return {"value": metadata}
