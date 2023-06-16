MilvusStore
==================================
MilvusStore is one implementation of the Milvus vector database in VectorConnector.

[Tutorial on how to create a Milvus instance](https://milvus.io/docs/install_standalone-docker.md)

inheriting the VectorStoreBase and implement similar_search(), vector_name_exists(), load_document().
```
class MilvusStore(VectorStoreBase):
    """Milvus database"""

    def __init__(self, ctx: {}) -> None:
        """init a milvus storage connection.

        Args:
            ctx ({}): MilvusStore global config.
        """
        # self.configure(cfg)

        connect_kwargs = {}
        self.uri = CFG.MILVUS_URL
        self.port = CFG.MILVUS_PORT
        self.username = CFG.MILVUS_USERNAME
        self.password = CFG.MILVUS_PASSWORD
        self.collection_name = ctx.get("vector_store_name", None)
        self.secure = ctx.get("secure", None)
        self.embedding = ctx.get("embeddings", None)
        self.fields = []
        self.alias = "default"
        )
```

similar_search()

```
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

```

vector_name_exists()

```
   def vector_name_exists(self):
        """is vector store name exist."""
        return utility.has_collection(self.collection_name)

```

load_document()

```
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
```

