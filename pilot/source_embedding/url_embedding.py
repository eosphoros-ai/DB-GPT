from typing import List

from bs4 import BeautifulSoup
from langchain.document_loaders import WebBaseLoader
from langchain.schema import Document
from langchain.text_splitter import CharacterTextSplitter

from pilot.configs.config import Config
from pilot.configs.model_config import KNOWLEDGE_CHUNK_SPLIT_SIZE
from pilot.source_embedding import SourceEmbedding, register
from pilot.source_embedding.chn_document_splitter import CHNDocumentSplitter

CFG = Config()


class URLEmbedding(SourceEmbedding):
    """url embedding for read url document."""

    def __init__(self, file_path, vector_store_config):
        """Initialize with url path."""
        super().__init__(file_path, vector_store_config)
        self.file_path = file_path
        self.vector_store_config = vector_store_config

    @register
    def read(self):
        """Load from url path."""
        loader = WebBaseLoader(web_path=self.file_path)
        if CFG.LANGUAGE == "en":
            text_splitter = CharacterTextSplitter(
                chunk_size=CFG.KNOWLEDGE_CHUNK_SIZE,
                chunk_overlap=20,
                length_function=len,
            )
        else:
            text_splitter = CHNDocumentSplitter(pdf=True, sentence_size=1000)
        return loader.load_and_split(text_splitter)

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            content = d.page_content.replace("\n", "")
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["!doctype", "meta"]):
                tag.extract()
            documents[i].page_content = soup.get_text()
            i += 1
        return documents
