from pilot.source_embedding.pdf_embedding import PDFEmbedding

path = "xxx.pdf"
model_name = "/Users/chenketing/Desktop/project/all-MiniLM-L6-v2"
vector_store_path = "/pilot/source_embedding/"


pdf_embedding = PDFEmbedding(file_path=path, model_name=model_name, vector_store_config={"vector_store_name": "ob", "vector_store_path": "vector_store_path"})
pdf_embedding.source_embedding()
print("success")