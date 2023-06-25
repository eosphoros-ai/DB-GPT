from pilot.embedding_engine.pdf_embedding import PDFEmbedding

path = "xxx.pdf"
path = "your_path/OceanBase-数据库-V4.1.0-应用开发.pdf"
model_name = "your_path/all-MiniLM-L6-v2"
vector_store_path = "your_path/"


pdf_embedding = PDFEmbedding(
    file_path=path,
    model_name=model_name,
    vector_store_config={
        "vector_store_name": "ob-pdf",
        "vector_store_path": vector_store_path,
    },
)
pdf_embedding.source_embedding()
print("success")
