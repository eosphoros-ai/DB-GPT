ChromaStore
==================================
ChromaStore is one implementation of the Chroma vector database in VectorConnector.

inheriting the VectorStoreBase and implement similar_search(), vector_name_exists(), load_document().
```
class ChromaStore(VectorStoreBase):
    """chroma database"""

    def __init__(self, ctx: {}) -> None:
        self.ctx = ctx
        self.embeddings = ctx["embeddings"]
        self.persist_dir = os.path.join(
            KNOWLEDGE_UPLOAD_ROOT_PATH, ctx["vector_store_name"] + ".vectordb"
        )
        self.vector_store_client = Chroma(
            persist_directory=self.persist_dir, embedding_function=self.embeddings
        )
```

similar_search()

```
  def similar_search(self, text, topk) -> None:
        logger.info("ChromaStore similar search")
        return self.vector_store_client.similarity_search(text, topk)

```

vector_name_exists()

```
 def vector_name_exists(self):
        return (
            os.path.exists(self.persist_dir) and len(os.listdir(self.persist_dir)) > 0
        )

```

load_document()

```
  def load_document(self, documents):
        logger.info("ChromaStore load document")
        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        self.vector_store_client.add_texts(texts=texts, metadatas=metadatas)
        self.vector_store_client.persist()
```

