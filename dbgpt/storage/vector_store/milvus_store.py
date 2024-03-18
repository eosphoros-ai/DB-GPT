"""Milvus vector store."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable, List, Optional

from dbgpt._private.pydantic import Field
from dbgpt.core import Chunk, Embeddings
from dbgpt.storage.vector_store.base import VectorStoreBase, VectorStoreConfig
from dbgpt.util import string_utils

logger = logging.getLogger(__name__)


class MilvusVectorConfig(VectorStoreConfig):
    """Milvus vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    uri: str = Field(
        default="localhost",
        description="The uri of milvus store, if not set, will use the default uri.",
    )
    port: str = Field(
        default="19530",
        description="The port of milvus store, if not set, will use the default port.",
    )

    alias: str = Field(
        default="default",
        description="The alias of milvus store, if not set, will use the default "
        "alias.",
    )
    user: str = Field(
        default=None,
        description="The user of milvus store, if not set, will use the default user.",
    )
    password: str = Field(
        default=None,
        description="The password of milvus store, if not set, will use the default "
        "password.",
    )
    primary_field: str = Field(
        default="pk_id",
        description="The primary field of milvus store, if not set, will use the "
        "default primary field.",
    )
    text_field: str = Field(
        default="content",
        description="The text field of milvus store, if not set, will use the default "
        "text field.",
    )
    embedding_field: str = Field(
        default="vector",
        description="The embedding field of milvus store, if not set, will use the "
        "default embedding field.",
    )
    metadata_field: str = Field(
        default="metadata",
        description="The metadata field of milvus store, if not set, will use the "
        "default metadata field.",
    )
    secure: str = Field(
        default="",
        description="The secure of milvus store, if not set, will use the default "
        "secure.",
    )


class MilvusStore(VectorStoreBase):
    """Milvus vector store."""

    def __init__(self, vector_store_config: MilvusVectorConfig) -> None:
        """Create a MilvusStore instance.

        Args:
            vector_store_config (MilvusVectorConfig): MilvusStore config.
            refer to https://milvus.io/docs/v2.0.x/manage_connection.md
        """
        from pymilvus import connections

        connect_kwargs = {}
        milvus_vector_config = vector_store_config.dict()
        self.uri = milvus_vector_config.get("uri") or os.getenv(
            "MILVUS_URL", "localhost"
        )
        self.port = milvus_vector_config.get("post") or os.getenv(
            "MILVUS_PORT", "19530"
        )
        self.username = milvus_vector_config.get("user") or os.getenv("MILVUS_USERNAME")
        self.password = milvus_vector_config.get("password") or os.getenv(
            "MILVUS_PASSWORD"
        )
        self.secure = milvus_vector_config.get("secure") or os.getenv("MILVUS_SECURE")

        self.collection_name = (
            milvus_vector_config.get("name") or vector_store_config.name
        )
        if string_utils.is_all_chinese(self.collection_name):
            bytes_str = self.collection_name.encode("utf-8")
            hex_str = bytes_str.hex()
            self.collection_name = hex_str

        if not vector_store_config.embedding_fn:
            raise ValueError("embedding is required for MilvusStore")

        self.embedding: Embeddings = vector_store_config.embedding_fn
        self.fields: List = []
        self.alias = milvus_vector_config.get("alias") or "default"

        # use HNSW by default.
        self.index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 8, "efConstruction": 64},
        }

        # use HNSW by default.
        self.index_params_map = {
            "IVF_FLAT": {"params": {"nprobe": 10}},
            "IVF_SQ8": {"params": {"nprobe": 10}},
            "IVF_PQ": {"params": {"nprobe": 10}},
            "HNSW": {"params": {"M": 8, "efConstruction": 64}},
            "RHNSW_FLAT": {"params": {"ef": 10}},
            "RHNSW_SQ": {"params": {"ef": 10}},
            "RHNSW_PQ": {"params": {"ef": 10}},
            "IVF_HNSW": {"params": {"nprobe": 10, "ef": 10}},
            "ANNOY": {"params": {"search_k": 10}},
        }
        # default collection schema
        self.primary_field = milvus_vector_config.get("primary_field") or "pk_id"
        self.vector_field = milvus_vector_config.get("embedding_field") or "vector"
        self.text_field = milvus_vector_config.get("text_field") or "content"
        self.metadata_field = milvus_vector_config.get("metadata_field") or "metadata"

        if (self.username is None) != (self.password is None):
            raise ValueError(
                "Both username and password must be set to use authentication for "
                "Milvus"
            )
        if self.username:
            connect_kwargs["user"] = self.username
            connect_kwargs["password"] = self.password

        connections.connect(
            host=self.uri or "127.0.0.1",
            port=self.port or "19530",
            user=self.username,
            password=self.password,
            alias="default",
        )

    def init_schema_and_load(self, vector_name, documents) -> List[str]:
        """Create a Milvus collection.

        Create a Milvus collection, indexes it with HNSW, load document.

        Args:
            vector_name (Embeddings): your collection name.
            documents (List[str]): Text to insert.
        Returns:
            List[str]: document ids.
        """
        try:
            from pymilvus import (
                Collection,
                CollectionSchema,
                DataType,
                FieldSchema,
                connections,
                utility,
            )
            from pymilvus.orm.types import infer_dtype_bydata  # noqa: F401
        except ImportError:
            raise ValueError(
                "Could not import pymilvus python package. "
                "Please install it with `pip install pymilvus`."
            )
        if not connections.has_connection("default"):
            connections.connect(
                host=self.uri or "127.0.0.1",
                port=self.port or "19530",
                alias="default",
                # secure=self.secure,
            )
        texts = [d.content for d in documents]
        metadatas = [d.metadata for d in documents]
        embeddings = self.embedding.embed_query(texts[0])

        if utility.has_collection(self.collection_name):
            self.col = Collection(self.collection_name, using=self.alias)
            self.fields = []
            for x in self.col.schema.fields:
                self.fields.append(x.name)
                if x.auto_id:
                    self.fields.remove(x.name)
                if x.is_primary:
                    self.primary_field = x.name
                if (
                    x.dtype == DataType.FLOAT_VECTOR
                    or x.dtype == DataType.BINARY_VECTOR
                ):
                    self.vector_field = x.name
            return self._add_documents(texts, metadatas)
            # return self.collection_name

        dim = len(embeddings)
        # Generate unique names
        primary_field = self.primary_field
        vector_field = self.vector_field
        text_field = self.text_field
        metadata_field = self.metadata_field
        # self.text_field = text_field
        collection_name = vector_name
        fields = []
        max_length = 0
        for y in texts:
            max_length = max(max_length, len(y))
        # Create the text field
        fields.append(FieldSchema(text_field, DataType.VARCHAR, max_length=65535))
        # primary key field
        fields.append(
            FieldSchema(primary_field, DataType.INT64, is_primary=True, auto_id=True)
        )
        # vector field
        fields.append(FieldSchema(vector_field, DataType.FLOAT_VECTOR, dim=dim))

        fields.append(FieldSchema(metadata_field, DataType.VARCHAR, max_length=65535))
        schema = CollectionSchema(fields)
        # Create the collection
        collection = Collection(collection_name, schema)
        self.col = collection
        # index parameters for the collection
        index = self.index_params
        # milvus index
        collection.create_index(vector_field, index)
        collection.load()
        schema = collection.schema
        for x in schema.fields:
            self.fields.append(x.name)
            if x.auto_id:
                self.fields.remove(x.name)
            if x.is_primary:
                self.primary_field = x.name
            if x.dtype == DataType.FLOAT_VECTOR or x.dtype == DataType.BINARY_VECTOR:
                self.vector_field = x.name
        ids = self._add_documents(texts, metadatas)

        return ids

    def _add_documents(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        partition_name: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> List[str]:
        """Add text data into Milvus."""
        insert_dict: Any = {self.text_field: list(texts)}
        try:
            import numpy as np  # noqa: F401

            text_vector = self.embedding.embed_documents(list(texts))
            insert_dict[self.vector_field] = text_vector
        except NotImplementedError:
            insert_dict[self.vector_field] = [
                self.embedding.embed_query(x) for x in texts
            ]
        # Collect the metadata into the insert dict.
        # self.fields.extend(metadatas[0].keys())
        if len(self.fields) > 2 and metadatas is not None:
            for d in metadatas:
                # for key, value in d.items():
                insert_dict.setdefault("metadata", []).append(json.dumps(d))
        # Convert dict to list of lists for insertion
        insert_list = [insert_dict[x] for x in self.fields]
        # Insert into the collection.
        res = self.col.insert(
            insert_list, partition_name=partition_name, timeout=timeout
        )
        # make sure data is searchable.
        self.col.flush()
        return res.primary_keys

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in vector database."""
        batch_size = 500
        batched_list = [
            chunks[i : i + batch_size] for i in range(0, len(chunks), batch_size)
        ]
        doc_ids = []
        for doc_batch in batched_list:
            doc_ids.extend(self.init_schema_and_load(self.collection_name, doc_batch))
        doc_ids = [str(doc_id) for doc_id in doc_ids]
        return doc_ids

    def similar_search(self, text, topk) -> List[Chunk]:
        """Perform a search on a query string and return results."""
        from pymilvus import Collection, DataType

        """similar_search in vector database."""
        self.col = Collection(self.collection_name)
        schema = self.col.schema
        for x in schema.fields:
            self.fields.append(x.name)
            if x.auto_id:
                self.fields.remove(x.name)
            if x.is_primary:
                self.primary_field = x.name
            if x.dtype == DataType.FLOAT_VECTOR or x.dtype == DataType.BINARY_VECTOR:
                self.vector_field = x.name
        _, docs_and_scores = self._search(text, topk)

        return [
            Chunk(
                metadata=json.loads(doc.metadata.get("metadata", "")),
                content=doc.content,
            )
            for doc, _, _ in docs_and_scores
        ]

    def similar_search_with_scores(self, text, topk, score_threshold) -> List[Chunk]:
        """Perform a search on a query string and return results with score.

        For more information about the search parameters, take a look at the pymilvus
        documentation found here:
        https://milvus.io/api-reference/pymilvus/v2.2.6/Collection/search().md

        Args:
            embedding (List[float]): The embedding vector being searched.
            k (int, optional): The amount of results to return. Defaults to 4.
            param (dict): The search params for the specified index.
                Defaults to None.
            expr (str, optional): Filtering expression. Defaults to None.
            timeout (int, optional): How long to wait before timeout error.
                Defaults to None.
            kwargs: Collection.search() keyword arguments.

        Returns:
            List[Tuple[Document, float]]: Result doc and score.
        """
        from pymilvus import Collection

        self.col = Collection(self.collection_name)
        schema = self.col.schema
        for x in schema.fields:
            self.fields.append(x.name)
            if x.auto_id:
                self.fields.remove(x.name)
            if x.is_primary:
                self.primary_field = x.name
            from pymilvus import DataType

            if x.dtype == DataType.FLOAT_VECTOR or x.dtype == DataType.BINARY_VECTOR:
                self.vector_field = x.name
        _, docs_and_scores = self._search(text, topk)
        if any(score < 0.0 or score > 1.0 for _, score, id in docs_and_scores):
            logger.warning(
                "similarity score need between" f" 0 and 1, got {docs_and_scores}"
            )

        if score_threshold is not None:
            docs_and_scores = [
                Chunk(
                    metadata=doc.metadata,
                    content=doc.content,
                    score=score,
                    chunk_id=id,
                )
                for doc, score, id in docs_and_scores
                if score >= score_threshold
            ]
            if len(docs_and_scores) == 0:
                logger.warning(
                    "No relevant docs were retrieved using the relevance score"
                    f" threshold {score_threshold}"
                )
        return docs_and_scores

    def _search(
        self,
        query: str,
        k: int = 4,
        param: Optional[dict] = None,
        expr: Optional[str] = None,
        partition_names: Optional[List[str]] = None,
        round_decimal: int = -1,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ):
        self.col.load()
        # use default index params.
        if param is None:
            index_type = self.col.indexes[0].params["index_type"]
            param = self.index_params_map[index_type].get("params")
        #  query text embedding.
        query_vector = self.embedding.embed_query(query)
        # Determine result metadata fields.
        output_fields = self.fields[:]
        output_fields.remove(self.vector_field)
        # milvus search.
        res = self.col.search(
            [query_vector],
            self.vector_field,
            param,
            k,
            expr=expr,
            output_fields=output_fields,
            partition_names=partition_names,
            round_decimal=round_decimal,
            timeout=60,
            **kwargs,
        )
        ret = []
        for result in res[0]:
            meta = {x: result.entity.get(x) for x in output_fields}
            ret.append(
                (
                    Chunk(content=meta.pop(self.text_field), metadata=meta),
                    result.distance,
                    result.id,
                )
            )

        return ret[0], ret

    def vector_name_exists(self):
        """Whether vector name exists."""
        from pymilvus import utility

        """is vector store name exist."""
        return utility.has_collection(self.collection_name)

    def delete_vector_name(self, vector_name: str):
        """Delete vector name."""
        from pymilvus import utility

        """milvus delete collection name"""
        logger.info(f"milvus vector_name:{vector_name} begin delete...")
        utility.drop_collection(self.collection_name)
        return True

    def delete_by_ids(self, ids):
        """Delete vector by ids."""
        from pymilvus import Collection

        self.col = Collection(self.collection_name)
        # milvus delete vectors by ids
        logger.info(f"begin delete milvus ids: {ids}")
        delete_ids = ids.split(",")
        doc_ids = [int(doc_id) for doc_id in delete_ids]
        delet_expr = f"{self.primary_field} in {doc_ids}"
        self.col.delete(delet_expr)
        return True
