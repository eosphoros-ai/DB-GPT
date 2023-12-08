from dbgpt import EmbeddingEngine, KnowledgeType

embedding_model = "your_embedding_model"
vector_store_type = "Chroma"
chroma_persist_path = "your_persist_path"
vector_store_config = {
    "vector_store_name": "document_test",
    "vector_store_type": vector_store_type,
    "chroma_persist_path": chroma_persist_path,
}

# it can be .md,.pdf,.docx, .csv, .html
document_path = "your_path/test.md"
embedding_engine = EmbeddingEngine(
    knowledge_source=document_path,
    knowledge_type=KnowledgeType.DOCUMENT.value,
    model_name=embedding_model,
    vector_store_config=vector_store_config,
)
# embedding document content to vector store
embedding_engine.knowledge_embedding()
