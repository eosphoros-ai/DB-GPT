WeaviateStore
==================================
WeaviateStore is one implementation of the Milvus vector database in VectorConnector.

[Tutorial on how to create a Weaviate instance](https://weaviate.io/developers/weaviate/installation)

inheriting the VectorStoreBase and implement similar_search(), vector_name_exists(), load_document().
```
class WeaviateStore(VectorStoreBase):
    """Weaviate database"""

    def __init__(self, ctx: dict) -> None:
        """Initialize with Weaviate client."""
        try:
            import weaviate
        except ImportError:
            raise ValueError(
                "Could not import weaviate python package. "
                "Please install it with `pip install weaviate-client`."
            )

        self.ctx = ctx
        self.weaviate_url = CFG.WEAVIATE_URL
        self.embedding = ctx.get("embeddings", None)
        self.vector_name = ctx["vector_store_name"]
        self.persist_dir = os.path.join(
            KNOWLEDGE_UPLOAD_ROOT_PATH, self.vector_name + ".vectordb"
        )

        self.vector_store_client = weaviate.Client(self.weaviate_url)
```

similar_search()

```
   def similar_search(self, text: str, topk: int) -> None:
        """Perform similar search in Weaviate"""
        logger.info("Weaviate similar search")
        # nearText = {
        #     "concepts": [text],
        #     "distance": 0.75,  # prior to v1.14 use "certainty" instead of "distance"
        # }
        # vector = self.embedding.embed_query(text)
        response = (
            self.vector_store_client.query.get(self.vector_name, ["metadata", "page_content"])
            # .with_near_vector({"vector": vector})
            .with_limit(topk)
            .do()
        )
        docs = response['data']['Get'][list(response['data']['Get'].keys())[0]]
        return docs

```

vector_name_exists()

```
  def vector_name_exists(self) -> bool:
        """Check if a vector name exists for a given class in Weaviate.
        Returns:
            bool: True if the vector name exists, False otherwise.
        """
        if self.vector_store_client.schema.get(self.vector_name):
            return True
        return False

```

load_document()

```
    def load_document(self, documents: list) -> None:
        """Load documents into Weaviate"""
        logger.info("Weaviate load document")
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # Import data
        with self.vector_store_client.batch as batch:
            batch.batch_size = 100

            # Batch import all documents
            for i in range(len(texts)):
                properties = {"metadata": metadatas[i]['source'], "page_content": texts[i]}

                self.vector_store_client.batch.add_data_object(data_object=properties, class_name=self.vector_name)
            self.vector_store_client.batch.flush()
```

