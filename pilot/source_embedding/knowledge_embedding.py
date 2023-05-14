from pilot.source_embedding.csv_embedding import CSVEmbedding
from pilot.source_embedding.markdown_embedding import MarkdownEmbedding
from pilot.source_embedding.pdf_embedding import PDFEmbedding


class KnowledgeEmbedding:
    @staticmethod
    def knowledge_embedding(file_path:str, model_name, vector_store_config):
        if file_path.endswith(".pdf"):
            embedding = PDFEmbedding(file_path=file_path, model_name=model_name,
                                     vector_store_config=vector_store_config)
        elif file_path.endswith(".md"):
            embedding = MarkdownEmbedding(file_path=file_path, model_name=model_name,
                                     vector_store_config=vector_store_config)

        elif file_path.endswith(".csv"):
            embedding = CSVEmbedding(file_path=file_path, model_name=model_name,
                                     vector_store_config=vector_store_config)

        return embedding