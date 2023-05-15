from pilot.source_embedding.csv_embedding import CSVEmbedding
from pilot.source_embedding.markdown_embedding import MarkdownEmbedding
from pilot.source_embedding.pdf_embedding import PDFEmbedding


class KnowledgeEmbedding:
    def __init__(self, file_path, model_name, vector_store_config):
        """Initialize with Loader url, model_name, vector_store_config"""
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config
        self.vector_store_type = "default"
        self.knowledge_embedding_client = self.init_knowledge_embedding()

    def knowledge_embedding(self):
        self.knowledge_embedding_client.source_embedding()

    def init_knowledge_embedding(self):
        if self.file_path.endswith(".pdf"):
            embedding = PDFEmbedding(file_path=self.file_path, model_name=self.model_name,
                                     vector_store_config=self.vector_store_config)
        elif self.file_path.endswith(".md"):
            embedding = MarkdownEmbedding(file_path=self.file_path, model_name=self.model_name, vector_store_config=self.vector_store_config)

        elif self.file_path.endswith(".csv"):
            embedding = CSVEmbedding(file_path=self.file_path, model_name=self.model_name,
                                     vector_store_config=self.vector_store_config)
        elif self.vector_store_type == "default":
            embedding = MarkdownEmbedding(file_path=self.file_path, model_name=self.model_name, vector_store_config=self.vector_store_config)

        return embedding

    def similar_search(self, text, topk):
        return self.knowledge_embedding_client.similar_search(text, topk)