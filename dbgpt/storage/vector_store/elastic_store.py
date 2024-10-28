"""Elasticsearch vector store."""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from dbgpt._private.pydantic import Field
from dbgpt.core import Chunk, Embeddings
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util import string_utils
from dbgpt.util.i18n_utils import _

logger = logging.getLogger(__name__)


@register_resource(
    _("ElasticSearch Vector Store"),
    "elasticsearch_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("Uri"),
            "uri",
            str,
            description=_(
                "The uri of elasticsearch store, if not set, will use the default "
                "uri."
            ),
            optional=True,
            default="localhost",
        ),
        Parameter.build_from(
            _("Port"),
            "port",
            str,
            description=_(
                "The port of elasticsearch store, if not set, will use the default "
                "port."
            ),
            optional=True,
            default="9200",
        ),
        Parameter.build_from(
            _("Alias"),
            "alias",
            str,
            description=_(
                "The alias of elasticsearch store, if not set, will use the default "
                "alias."
            ),
            optional=True,
            default="default",
        ),
        Parameter.build_from(
            _("Index Name"),
            "index_name",
            str,
            description=_(
                "The index name of elasticsearch store, if not set, will use the "
                "default index name."
            ),
            optional=True,
            default="index_name_test",
        ),
    ],
    description=_("Elasticsearch vector store."),
)
class ElasticsearchVectorConfig(VectorStoreConfig):
    """Elasticsearch vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    uri: str = Field(
        default="localhost",
        description="The uri of elasticsearch store, if not set, will use the default "
        "uri.",
    )
    port: str = Field(
        default="9200",
        description="The port of elasticsearch store, if not set, will use the default "
        "port.",
    )

    alias: str = Field(
        default="default",
        description="The alias of elasticsearch store, if not set, will use the "
        "default "
        "alias.",
    )
    index_name: str = Field(
        default="index_name_test",
        description="The index name of elasticsearch store, if not set, will use the "
        "default index name.",
    )
    metadata_field: str = Field(
        default="metadata",
        description="The metadata field of elasticsearch store, if not set, will use "
        "the default metadata field.",
    )
    secure: str = Field(
        default="",
        description="The secure of elasticsearch store, if not set, will use the "
        "default secure.",
    )


class ElasticStore(VectorStoreBase):
    """Elasticsearch vector store."""

    def __init__(self, vector_store_config: ElasticsearchVectorConfig) -> None:
        """Create a ElasticsearchStore instance.

        Args:
            vector_store_config (ElasticsearchVectorConfig): ElasticsearchStore config.
        """
        super().__init__()
        self._vector_store_config = vector_store_config

        connect_kwargs = {}
        elasticsearch_vector_config = vector_store_config.dict()
        self.uri = os.getenv(
            "ELASTICSEARCH_URL", "localhost"
        ) or elasticsearch_vector_config.get("uri")
        self.port = os.getenv(
            "ELASTICSEARCH_PORT", "9200"
        ) or elasticsearch_vector_config.get("post")
        self.username = os.getenv(
            "ELASTICSEARCH_USERNAME"
        ) or elasticsearch_vector_config.get("username")
        self.password = os.getenv(
            "ELASTICSEARCH_PASSWORD"
        ) or elasticsearch_vector_config.get("password")

        self.collection_name = (
            elasticsearch_vector_config.get("name") or vector_store_config.name
        )
        # name to hex
        if string_utils.contains_chinese(self.collection_name):
            bytes_str = self.collection_name.encode("utf-8")
            hex_str = bytes_str.hex()
            self.collection_name = hex_str
        if vector_store_config.embedding_fn is None:
            # Perform runtime checks on self.embedding to
            # ensure it has been correctly set and loaded
            raise ValueError("embedding_fn is required for ElasticSearchStore")
        # to lower case
        self.index_name = self.collection_name.lower()
        self.embedding: Embeddings = vector_store_config.embedding_fn
        self.fields: List = []

        if (self.username is None) != (self.password is None):
            raise ValueError(
                "Both username and password must be set to use authentication for "
                "ElasticSearch"
            )

        if self.username:
            connect_kwargs["username"] = self.username
            connect_kwargs["password"] = self.password

        # english index settings
        self.index_settings = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,  # replica number
            }
        }
        """"""
        try:
            from elasticsearch import Elasticsearch
            from langchain.vectorstores.elasticsearch import ElasticsearchStore
        except ImportError:
            raise ValueError(
                "Could not import langchain and elasticsearch python package. "
                "Please install it with `pip install langchain` and "
                "`pip install elasticsearch`."
            )
        try:
            if self.username != "" and self.password != "":
                self.es_client_python = Elasticsearch(
                    f"http://{self.uri}:{self.port}",
                    basic_auth=(self.username, self.password),
                )
                # create es index
                if not self.vector_name_exists():
                    self.es_client_python.indices.create(
                        index=self.index_name, body=self.index_settings
                    )
            else:
                logger.warning("ElasticSearch not set username and password")
                self.es_client_python = Elasticsearch(f"http://{self.uri}:{self.port}")
                if not self.vector_name_exists():
                    self.es_client_python.indices.create(
                        index=self.index_name, body=self.index_settings
                    )
        except ConnectionError:
            logger.error("ElasticSearch connection failed")
        except Exception as e:
            logger.error(f"ElasticSearch connection failed : {e}")

        # create es index
        try:
            if self.username != "" and self.password != "":
                self.db_init = ElasticsearchStore(
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    query_field="context",
                    vector_query_field="dense_vector",
                    embedding=self.embedding,  # type: ignore
                    es_user=self.username,
                    es_password=self.password,
                )
            else:
                logger.warning("ElasticSearch not set username and password")
                self.db_init = ElasticsearchStore(
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    query_field="context",
                    vector_query_field="dense_vector",
                    embedding=self.embedding,  # type: ignore
                )
        except ConnectionError:
            logger.error("ElasticSearch connection failed")
        except Exception as e:
            logger.error(f"ElasticSearch connection failed: {e}")

    def get_config(self) -> ElasticsearchVectorConfig:
        """Get the vector store config."""
        return self._vector_store_config

    def load_document(
        self,
        chunks: List[Chunk],
    ) -> List[str]:
        """Add text data into ElasticSearch."""
        logger.info("ElasticStore load document")
        try:
            from langchain.vectorstores.elasticsearch import ElasticsearchStore
        except ImportError:
            raise ValueError(
                "Could not import langchain python package. "
                "Please install it with `pip install langchain` and "
                "`pip install elasticsearch`."
            )
        try:
            texts = [chunk.content for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]
            ids = [chunk.chunk_id for chunk in chunks]
            if self.username != "" and self.password != "":
                self.db = ElasticsearchStore.from_texts(
                    texts=texts,
                    embedding=self.embedding,  # type: ignore
                    metadatas=metadatas,
                    ids=ids,
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    # Defaults to COSINE. Can be one of COSINE, EUCLIDEAN_DISTANCE
                    # , or DOT_PRODUCT.
                    distance_strategy="COSINE",
                    # Name of the field to store the texts in.
                    query_field="context",
                    # Optional. Name of the field to store the embedding vectors in.
                    vector_query_field="dense_vector",
                    # verify_certs=False,
                    # strategy: Optional. Retrieval strategy to use when searching the
                    # index.
                    # Defaults to ApproxRetrievalStrategy.
                    # Can be one of ExactRetrievalStrategy, ApproxRetrievalStrategy,
                    # or SparseRetrievalStrategy.
                    es_user=self.username,
                    es_password=self.password,
                )  # type: ignore
                logger.info("Elasticsearch save success.......")
                return ids
            else:
                self.db = ElasticsearchStore.from_documents(
                    texts=texts,
                    embedding=self.embedding,  # type: ignore
                    metadatas=metadatas,
                    ids=ids,
                    es_url=f"http://{self.uri}:{self.port}",
                    index_name=self.index_name,
                    distance_strategy="COSINE",
                    query_field="context",
                    vector_query_field="dense_vector",
                    # verify_certs=False,
                )  # type: ignore
                return ids
        except ConnectionError as ce:
            logger.error(f"ElasticSearch connect failed {ce}")
        except Exception as e:
            logger.error(f"ElasticSearch load_document failed : {e}")
        return []

    def delete_by_ids(self, ids):
        """Delete vector by ids."""
        logger.info(f"begin delete elasticsearch len ids: {len(ids)}")
        ids = ids.split(",")
        try:
            self.db_init.delete(ids=ids)
            self.es_client_python.indices.refresh(index=self.index_name)
        except Exception as e:
            logger.error(f"ElasticSearch delete_by_ids failed : {e}")

    def similar_search(
        self,
        text: str,
        topk: int,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Perform a search on a query string and return results."""
        info_docs = self._search(query=text, topk=topk, filters=filters)
        return info_docs

    def similar_search_with_scores(
        self, text, topk, score_threshold, filters: Optional[MetadataFilters] = None
    ) -> List[Chunk]:
        """Perform a search on a query string and return results with score.

        For more information about the search parameters, take a look at the
        ElasticSearch documentation found here: https://www.elastic.co/.

        Args:
            text (str): The query text.
            topk (int): The number of similar documents to return.
            score_threshold (float): Optional, a floating point value between 0 to 1.
            filters (Optional[MetadataFilters]): Optional, metadata filters.
        Returns:
            List[Chunk]: Result doc and score.
        """
        query = text
        info_docs = self._search(query=query, topk=topk, filters=filters)
        docs_and_scores = [
            chunk for chunk in info_docs if chunk.score >= score_threshold
        ]
        if len(docs_and_scores) == 0:
            logger.warning(
                "No relevant docs were retrieved using the relevance score"
                f" threshold {score_threshold}"
            )
        return docs_and_scores

    def _search(
        self, query: str, topk: int, filters: Optional[MetadataFilters] = None, **kwargs
    ) -> List[Chunk]:
        """Search similar documents.

        Args:
            query: query text
            topk: return docs nums. Defaults to 4.
            filters: metadata filters.
        Return:
            List[Chunk]: list of chunks
        """
        jieba_tokenize = kwargs.pop("jieba_tokenize", None)
        if jieba_tokenize:
            try:
                import jieba
                import jieba.analyse
            except ImportError:
                raise ValueError("Please install it with `pip install jieba`.")
            query_list = jieba.analyse.textrank(query, topK=20, withWeight=False)
            query = " ".join(query_list)
        body = {"query": {"match": {"context": query}}}
        search_results = self.es_client_python.search(
            index=self.index_name, body=body, size=topk
        )
        search_results = search_results["hits"]["hits"]

        if not search_results:
            logger.warning("""No ElasticSearch results found.""")
            return []
        info_docs = []
        for result in search_results:
            doc_id = result["_id"]
            source = result["_source"]
            context = source["context"]
            metadata = source["metadata"]
            score = result["_score"]
            doc_with_score = Chunk(
                content=context, metadata=metadata, score=score, chunk_id=doc_id
            )
            info_docs.append(doc_with_score)
        return info_docs

    def vector_name_exists(self):
        """Whether vector name exists."""
        return self.es_client_python.indices.exists(index=self.index_name)

    def delete_vector_name(self, vector_name: str):
        """Delete vector name/index_name."""
        if self.es_client_python.indices.exists(index=self.index_name):
            self.es_client_python.indices.delete(index=self.index_name)
