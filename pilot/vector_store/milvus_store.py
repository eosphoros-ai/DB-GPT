from typing import Any, Iterable, List, Optional, Tuple

from langchain.docstore.document import Document
from pymilvus import Collection, DataType, connections, utility

from pilot.vector_store.vector_store_base import VectorStoreBase




class MilvusStore(VectorStoreBase):
    """Milvus database"""

    def __init__(self, ctx: {}) -> None:
        """init a milvus storage connection.

        Args:
            ctx ({}): MilvusStore global config.
        """
        # self.configure(cfg)

        connect_kwargs = {}
        self.uri = ctx.get("milvus_url", None)
        self.port = ctx.get("milvus_port", None)
        self.username = ctx.get("milvus_username", None)
        self.password = ctx.get("milvus_password", None)
        self.collection_name = ctx.get("vector_store_name", None)
        self.secure = ctx.get("secure", None)
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
            self._add_documents(texts, metadatas)
            return self.collection_name

        dim = len(embeddings)
        # Generate unique names
        primary_field = self.primary_field
        vector_field = self.vector_field
        text_field = self.text_field
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
        schema = CollectionSchema(fields)
        # Create the collection
        collection = Collection(collection_name, schema)
        self.col = collection
        # index parameters for the collection
        index = self.index_params
        # milvus index
        collection.create_index(vector_field, index)
        schema = collection.schema
        for x in schema.fields:
            self.fields.append(x.name)
            if x.auto_id:
                self.fields.remove(x.name)
            if x.is_primary:
                self.primary_field = x.name
            if x.dtype == DataType.FLOAT_VECTOR or x.dtype == DataType.BINARY_VECTOR:
                self.vector_field = x.name
        self._add_documents(texts, metadatas)

        return self.collection_name

    # def init_schema(self) -> None:
    #     """Initialize collection in milvus database."""
    #     fields = [
    #         FieldSchema(name="pk", dtype=DataType.INT64, is_primary=True, auto_id=True),
    #         FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.model_config["dim"]),
    #         FieldSchema(name="raw_text", dtype=DataType.VARCHAR, max_length=65535),
    #     ]
    #
    #     # create collection if not exist and load it.
    #     self.schema = CollectionSchema(fields, "db-gpt memory storage")
    #     self.collection = Collection(self.collection_name, self.schema)
    #     self.index_params_map = {
    #         "IVF_FLAT": {"params": {"nprobe": 10}},
    #         "IVF_SQ8": {"params": {"nprobe": 10}},
    #         "IVF_PQ": {"params": {"nprobe": 10}},
    #         "HNSW": {"params": {"ef": 10}},
    #         "RHNSW_FLAT": {"params": {"ef": 10}},
    #         "RHNSW_SQ": {"params": {"ef": 10}},
    #         "RHNSW_PQ": {"params": {"ef": 10}},
    #         "IVF_HNSW": {"params": {"nprobe": 10, "ef": 10}},
    #         "ANNOY": {"params": {"search_k": 10}},
    #     }
    #
    #     self.index_params = {
    #         "metric_type": "IP",
    #         "index_type": "HNSW",
    #         "params": {"M": 8, "efConstruction": 64},
    #     }
    #     # create index if not exist.
    #     if not self.collection.has_index():
    #         self.collection.release()
    #         self.collection.create_index(
    #             "vector",
    #             self.index_params,
    #             index_name="vector",
    #         )
    #     info = self.collection.describe()
    #     self.collection.load()

    # def insert(self, text, model_config) -> str:
    #     """Add an embedding of data into milvus.
    #     Args:
    #         text (str): The raw text to construct embedding index.
    #     Returns:
    #         str: log.
    #     """
    #     # embedding = get_ada_embedding(data)
    #     embeddings = HuggingFaceEmbeddings(model_name=self.model_config["model_name"])
    #     result = self.collection.insert([embeddings.embed_documents(text), text])
    #     _text = (
    #         "Inserting data into memory at primary key: "
    #         f"{result.primary_keys[0]}:\n data: {text}"
    #     )
    #     return _text

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
            insert_dict[self.vector_field] = self.embedding.embed_documents(list(texts))
        except NotImplementedError:
            insert_dict[self.vector_field] = [
                self.embedding.embed_query(x) for x in texts
            ]
        # Collect the metadata into the insert dict.
        if len(self.fields) > 2 and metadatas is not None:
            for d in metadatas:
                for key, value in d.items():
                    if key in self.fields:
                        insert_dict.setdefault(key, []).append(value)
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
        # docs = []
        for doc_batch in batched_list:
            self.init_schema_and_load(self.collection_name, doc_batch)

    def similar_search(self, text, topk) -> None:
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
        return [doc for doc, _, _ in docs_and_scores]

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
    ) -> Tuple[List[float], List[Tuple[Document, Any, Any]]]:
        self.col.load()
        # use default index params.
        if param is None:
            index_type = self.col.indexes[0].params["index_type"]
            param = self.index_params_map[index_type]
        #  query text embedding.
        data = [self.embedding.embed_query(query)]
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
            timeout=timeout,
            **kwargs,
        )
        ret = []
        for result in res[0]:
            meta = {x: result.entity.get(x) for x in output_fields}
            ret.append(
                (
                    Document(page_content=meta.pop(self.text_field), metadata=meta),
                    result.distance,
                    result.id,
                )
            )

        return data[0], ret

    def vector_name_exists(self):
        """is vector store name exist."""
        return utility.has_collection(self.collection_name)

    def close(self):
        connections.disconnect()
