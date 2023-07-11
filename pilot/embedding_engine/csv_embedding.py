from typing import Dict, List, Optional

from langchain.document_loaders import CSVLoader
from langchain.schema import Document

from pilot.embedding_engine import SourceEmbedding, register


class CSVEmbedding(SourceEmbedding):
    """csv embedding for read csv document."""

    def __init__(self, file_path, vector_store_config, text_splitter=None):
        """Initialize with csv path."""
        super().__init__(file_path, vector_store_config, text_splitter=None)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.text_splitter = text_splitter or None

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
