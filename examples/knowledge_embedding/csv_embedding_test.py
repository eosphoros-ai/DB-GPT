from pilot.embedding_engine.csv_embedding import CSVEmbedding

# path = "/Users/chenketing/Downloads/share_ireserve双写数据异常2.xlsx"
path = "xx.csv"
model_name = "your_path/all-MiniLM-L6-v2"
vector_store_path = "your_path/"


pdf_embedding = CSVEmbedding(
    file_path=path,
    model_name=model_name,
    vector_store_config={
        "vector_store_name": "url",
        "vector_store_path": "vector_store_path",
    },
)
pdf_embedding.source_embedding()
print("success")
