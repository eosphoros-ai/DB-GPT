from typing import List

from langchain.schema import Document

from pilot import SourceEmbedding, register


class StringEmbedding(SourceEmbedding):
    """string embedding for read string document."""

    def __init__(self, file_path, vector_store_config):
        """Initialize with pdf path."""
        super().__init__(file_path, vector_store_config)
        self.file_path = file_path
        self.vector_store_config = vector_store_config

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
