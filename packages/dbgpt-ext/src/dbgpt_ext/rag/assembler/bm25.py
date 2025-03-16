"""BM25 Assembler."""

import json
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any, List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt_ext.rag.assembler.base import BaseAssembler
from dbgpt_ext.rag.chunk_manager import ChunkParameters
from dbgpt_ext.rag.retriever.bm25 import BM25Retriever
from dbgpt_ext.storage.vector_store.elastic_store import ElasticsearchStoreConfig


class BM25Assembler(BaseAssembler):
    """BM25 Assembler.

    refer https://www.elastic.co/guide/en/elasticsearch/reference/8.9/index-
    modules-similarity.html
    TF/IDF based similarity that has built-in tf normalization and is supposed to
    work better for short fields (like names). See Okapi_BM25 for more details.
    This similarity has the following options:

    Example:
    .. code-block:: python

        from dbgpt_ext.rag.assembler import BM25Assembler

        pdf_path = "path/to/document.pdf"
        knowledge = KnowledgeFactory.from_file_path(pdf_path)
        assembler = BM25Assembler.load_from_knowledge(
            knowledge=knowledge,
            es_config=es_config,
            chunk_parameters=chunk_parameters,
        )
        assembler.persist()
        # get bm25 retriever
        retriever = assembler.as_retriever(3)
        chunks = retriever.retrieve_with_scores("what is awel talk about", 0.3)
        print(f"bm25 rag example results:{chunks}")
    """

    def __init__(
        self,
        knowledge: Knowledge,
        es_config: ElasticsearchStoreConfig,
        name: Optional[str] = "dbgpt",
        k1: Optional[float] = 2.0,
        b: Optional[float] = 0.75,
        chunk_parameters: Optional[ChunkParameters] = None,
        executor: Optional[Executor] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with BM25 Assembler arguments.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            es_config: (ElasticsearchStoreConfig) Elasticsearch config.
            k1 (Optional[float]): Controls non-linear term frequency normalization
            (saturation). The default value is 2.0.
            b (Optional[float]): Controls to what degree document length normalizes
            tf values. The default value is 0.75.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
        """
        from elasticsearch import Elasticsearch

        self._es_config = es_config
        self._es_url = es_config.uri
        self._es_port = es_config.port
        self._es_username = es_config.user
        self._es_password = es_config.password
        self._index_name = name
        self._k1 = k1
        self._b = b
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
                    "k1": k1,
                    "b": b,
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

        self._executor = executor or ThreadPoolExecutor()
        if knowledge is None:
            raise ValueError("knowledge datasource must be provided.")
        if not self._es_client.indices.exists(index=self._index_name):
            self._es_client.indices.create(
                index=self._index_name,
                mappings=self._es_mappings,
                settings=self._es_index_settings,
            )
        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            **kwargs,
        )

    @classmethod
    def load_from_knowledge(
        cls,
        knowledge: Knowledge,
        es_config: ElasticsearchStoreConfig,
        name: Optional[str] = "dbgpt",
        k1: Optional[float] = 2.0,
        b: Optional[float] = 0.75,
        chunk_parameters: Optional[ChunkParameters] = None,
    ) -> "BM25Assembler":
        """Load document full text into elasticsearch from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            es_config: (ElasticsearchStoreConfig) Elasticsearch config.
            name: (Optional[str]) BM25 name.
            k1: (Optional[float]) BM25 parameter k1.
            b: (Optional[float]) BM25 parameter b.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.

        Returns:
             BM25Assembler
        """
        return cls(
            knowledge=knowledge,
            es_config=es_config,
            name=name,
            k1=k1,
            b=b,
            chunk_parameters=chunk_parameters,
        )

    @classmethod
    async def aload_from_knowledge(
        cls,
        knowledge: Knowledge,
        es_config: ElasticsearchStoreConfig,
        name: Optional[str] = "dbgpt",
        k1: Optional[float] = 2.0,
        b: Optional[float] = 0.75,
        chunk_parameters: Optional[ChunkParameters] = None,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> "BM25Assembler":
        """Load document full text into elasticsearch from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            es_config: (ElasticsearchStoreConfig) Elasticsearch config.
            k1: (Optional[float]) BM25 parameter k1.
            b: (Optional[float]) BM25 parameter b.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            executor: (Optional[ThreadPoolExecutor]) executor.

        Returns:
             BM25Assembler
        """
        return await blocking_func_to_async(
            executor,
            cls,
            knowledge,
            es_config=es_config,
            name=name,
            k1=k1,
            b=b,
            chunk_parameters=chunk_parameters,
        )

    def persist(self, **kwargs) -> List[str]:
        """Persist chunks into elasticsearch.

        Returns:
            List[str]: List of chunk ids.
        """
        try:
            from elasticsearch.helpers import bulk
        except ImportError:
            raise ValueError("Please install package `pip install elasticsearch`.")
        es_requests = []
        ids = []
        contents = [chunk.content for chunk in self._chunks]
        metadatas = [json.dumps(chunk.metadata) for chunk in self._chunks]
        chunk_ids = [chunk.chunk_id for chunk in self._chunks]
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

    async def apersist(self, **kwargs) -> List[str]:
        """Persist chunks into elasticsearch.

        Returns:
            List[str]: List of chunk ids.
        """
        return await blocking_func_to_async(self._executor, self.persist)

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""
        return []

    def as_retriever(self, top_k: int = 4, **kwargs) -> BM25Retriever:
        """Create a BM25Retriever.

        Args:
            top_k(int): default 4.

        Returns:
            BM25Retriever
        """
        return BM25Retriever(
            top_k=top_k, es_index=self._index_name, es_client=self._es_client
        )
