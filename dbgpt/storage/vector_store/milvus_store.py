from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable, List, Optional, Tuple


from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)


class MilvusStore(VectorStoreBase):
    """Milvus database"""

    def __init__(self, ctx: {}) -> None:
        """MilvusStore init."""
        from pymilvus import connections

        """init a milvus storage connection.

        Args:
            ctx ({}): MilvusStore global config.
        """
        # self.configure(cfg)

        connect_kwargs = {}
        self.uri = ctx.get("MILVUS_URL", os.getenv("MILVUS_URL"))
        self.port = ctx.get("MILVUS_PORT", os.getenv("MILVUS_PORT"))
        self.username = ctx.get("MILVUS_USERNAME", os.getenv("MILVUS_USERNAME"))
        self.password = ctx.get("MILVUS_PASSWORD", os.getenv("MILVUS_PASSWORD"))
        self.secure = ctx.get("MILVUS_SECURE", os.getenv("MILVUS_SECURE"))
        self.collection_name = ctx.get("vector_store_name", None)
        self.embedding = ctx.get("embeddings", None)
        self.fields = []
        self.alias = "default"

        # use HNSW by default.
        self.index_params = {
            "metric_type": "L2",
            "index_type": "HNSW",
            "params": {"M": 8, "efConstruction": 64},
        }
        # use HNSW by default.
        self.index_params_map = {
            "IVF_FLAT": {"params": {"nprobe": 10}},
            "IVF_SQ8": {"params": {"nprobe": 10}},
            "IVF_PQ": {"params": {"nprobe": 10}},
            "HNSW": {"params": {"ef": 10}},
            "RHNSW_FLAT": {"params": {"ef": 10}},
            "RHNSW_SQ": {"params": {"ef": 10}},
            "RHNSW_PQ": {"params": {"ef": 10}},
            "IVF_HNSW": {"params": {"nprobe": 10, "ef": 10}},
            "ANNOY": {"params": {"search_k": 10}},
        }
        # default collection schema
        self.primary_field = "pk_id"
        self.vector_field = "vector"
        self.text_field = "content"
        self.metadata_field = "metadata"

        if (self.username is None) != (self.password is None):
            raise ValueError(
                "Both username and password must be set to use authentication for Milvus"
            )
        if self.username:
            connect_kwargs["user"] = self.username
            connect_kwargs["password"] = self.password

        connections.connect(
            host=self.uri or "127.0.0.1",
            port=self.port or "19530",
            alias="default"
            # secure=self.secure,
        )

    def init_schema_and_load(self, vector_name, documents):
        """Create a Milvus collection, indexes it with HNSW, load document.
        Args:
            vector_name (Embeddings): your collection name.
            documents (List[str]): Text to insert.
        Returns:
            VectorStore: The MilvusStore vector store.
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
            from pymilvus.orm.types import infer_dtype_bydata
        except ImportError:
            raise ValueError(
                "Could not import pymilvus python package. "
                "Please install it with `pip install pymilvus`."
            )
        if not connections.has_connection("default"):
            connections.connect(
                host=self.uri or "127.0.0.1",
                port=self.port or "19530",
                alias="default"
                # secure=self.secure,
            )
        texts = [d.page_content for d in documents]
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
        """add text data into Milvus."""
        insert_dict: Any = {self.text_field: list(texts)}
        try:
            import numpy as np

            text_vector = self.embedding.embed_documents(list(texts))
            insert_dict[self.vector_field] = self._normalization_vectors(text_vector)
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

    def load_document(self, documents) -> None:
        """load document in vector database."""
        # self.init_schema_and_load(self.collection_name, documents)
        batch_size = 500
        batched_list = [
            documents[i : i + batch_size] for i in range(0, len(documents), batch_size)
        ]
        doc_ids = []
        for doc_batch in batched_list:
            doc_ids.extend(self.init_schema_and_load(self.collection_name, doc_batch))
        doc_ids = [str(doc_id) for doc_id in doc_ids]
        return doc_ids

    def similar_search(self, text, topk):
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
        from langchain.schema import Document

        return [
            Document(
                metadata=json.loads(doc.metadata.get("metadata", "")),
                page_content=doc.page_content,
            )
            for doc, _, _ in docs_and_scores
        ]

    def similar_search_with_scores(self, text, topk, score_threshold):
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
            import warnings

            warnings.warn(
                "similarity score need between" f" 0 and 1, got {docs_and_scores}"
            )

        if score_threshold is not None:
            docs_and_scores = [
                (doc, score)
                for doc, score, id in docs_and_scores
                if score >= score_threshold
            ]
            if len(docs_and_scores) == 0:
                warnings.warn(
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
        from langchain.docstore.document import Document

        self.col.load()
        # use default index params.
        if param is None:
            index_type = self.col.indexes[0].params["index_type"]
            param = self.index_params_map[index_type]
        #  query text embedding.
        query_vector = self.embedding.embed_query(query)
        data = [self._normalization_vectors(query_vector)]
        # Determine result metadata fields.
        output_fields = self.fields[:]
        output_fields.remove(self.vector_field)
        # milvus search.
        res = self.col.search(
            data,
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
                    Document(page_content=meta.pop(self.text_field), metadata=meta),
                    self._default_relevance_score_fn(result.distance),
                    result.id,
                )
            )

        return data[0], ret

    def vector_name_exists(self):
        from pymilvus import utility

        """is vector store name exist."""
        return utility.has_collection(self.collection_name)

    def delete_vector_name(self, vector_name):
        from pymilvus import utility

        """milvus delete collection name"""
        logger.info(f"milvus vector_name:{vector_name} begin delete...")
        utility.drop_collection(vector_name)
        return True

    def delete_by_ids(self, ids):
        from pymilvus import Collection

        self.col = Collection(self.collection_name)
        """milvus delete vectors by ids"""
        logger.info(f"begin delete milvus ids...")
        delete_ids = ids.split(",")
        doc_ids = [int(doc_id) for doc_id in delete_ids]
        delet_expr = f"{self.primary_field} in {doc_ids}"
        self.col.delete(delet_expr)
        return True
