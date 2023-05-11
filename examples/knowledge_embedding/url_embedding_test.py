from pilot.source_embedding.url_embedding import URLEmbedding

path = "https://www.understandingwar.org/backgrounder/russian-offensive-campaign-assessment-february-8-2023"
model_name = "/Users/chenketing/Desktop/project/all-MiniLM-L6-v2"
vector_store_path = "/pilot/source_embedding/"


pdf_embedding = URLEmbedding(file_path=path, model_name=model_name, vector_store_config={"vector_store_name": "url", "vector_store_path": "vector_store_path"})
pdf_embedding.source_embedding()
print("success")