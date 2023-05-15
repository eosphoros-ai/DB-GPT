from typing import List, Optional, Dict
from pilot.source_embedding import SourceEmbedding, register

from langchain.document_loaders import CSVLoader
from langchain.schema import Document


class CSVEmbedding(SourceEmbedding):
    """csv embedding for read csv document."""

    def __init__(self, file_path, model_name, vector_store_config, embedding_args: Optional[Dict] = None):
        """Initialize with csv path."""
        super().__init__(file_path, model_name, vector_store_config)
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config
        self.embedding_args = embedding_args

    @register
    def read(self):
        """Load from csv path."""
        loader = CSVLoader(file_path=self.file_path)
        return loader.load()

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            documents[i].page_content = d.page_content.replace("\n", "")
            i += 1
        return documents



