from pilot import EmbeddingEngine, KnowledgeType

url = "https://db-gpt.readthedocs.io/en/latest/getting_started/getting_started.html"
embedding_model = "text2vec"
vector_store_type = "Chroma"
chroma_persist_path = "your_persist_path"
vector_store_config = {
            "vector_store_name": url.replace(":", ""),
            "vector_store_type": vector_store_type,
            "chroma_persist_path": chroma_persist_path
        }
embedding_engine = EmbeddingEngine(knowledge_source=url, knowledge_type=KnowledgeType.URL.value, model_name=embedding_model, vector_store_config=vector_store_config)

# embedding url content to vector store
embedding_engine.knowledge_embedding()

