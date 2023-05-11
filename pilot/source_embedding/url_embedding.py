from typing import List
from pilot.source_embedding import SourceEmbedding, register

from bs4 import BeautifulSoup
from langchain.document_loaders import WebBaseLoader
from langchain.schema import Document



class URLEmbedding(SourceEmbedding):
    """url embedding for read url document."""

    def __init__(self, file_path, model_name, vector_store_config):
        """Initialize with url path."""
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config

    @register
    def read(self):
        """Load from url path."""
        loader = WebBaseLoader(web_path=self.file_path)
        return loader.load()

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            content = d.page_content.replace("\n", "")
            soup = BeautifulSoup(content, 'html.parser')
            for tag in soup(['!doctype', 'meta']):
                tag.extract()
            documents[i].page_content = soup.get_text()
            i += 1
        return documents



