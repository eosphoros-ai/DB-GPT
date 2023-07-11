from typing import List

from langchain.schema import Document

from pilot.embedding_engine import SourceEmbedding, register


class StringEmbedding(SourceEmbedding):
    """string embedding for read string document."""

    def __init__(self, file_path, vector_store_config, text_splitter=None):
        """Initialize raw text word path."""
        super().__init__(file_path, vector_store_config, text_splitter=None)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.text_splitter = text_splitter or None

    @register
    def read(self):
        """Load from String path."""
        metadata = {"source": "db_summary"}
        return [Document(page_content=self.file_path, metadata=metadata)]

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            documents[i].page_content = d.page_content.replace("\n", "")
            i += 1
        return documents
