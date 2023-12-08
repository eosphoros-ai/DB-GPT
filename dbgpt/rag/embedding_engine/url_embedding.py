from typing import List, Optional

from bs4 import BeautifulSoup
from langchain.document_loaders import WebBaseLoader
from langchain.schema import Document
from langchain.text_splitter import (
    SpacyTextSplitter,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)

from dbgpt.rag.embedding_engine import SourceEmbedding, register


class URLEmbedding(SourceEmbedding):
    """url embedding for read url document."""

    def __init__(
        self,
        file_path,
        vector_store_config,
        source_reader: Optional = None,
        text_splitter: Optional[TextSplitter] = None,
    ):
        """Initialize url word path.
        Args:
           - file_path: data source path
           - vector_store_config: vector store config params.
           - source_reader: Optional[BaseLoader]
           - text_splitter: Optional[TextSplitter]
        """
        super().__init__(
            file_path, vector_store_config, source_reader=None, text_splitter=None
        )
        self.file_path = file_path
        self.vector_store_config = vector_store_config or None
        self.source_reader = source_reader or None
        self.text_splitter = text_splitter or None

    @register
    def read(self):
        """Load from url path."""
        if self.source_reader is None:
            self.source_reader = WebBaseLoader(web_path=self.file_path)
        if self.text_splitter is None:
            try:
                self.text_splitter = SpacyTextSplitter(
                    pipeline="zh_core_web_sm",
                    chunk_size=100,
                    chunk_overlap=100,
                )
            except Exception:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=100, chunk_overlap=50
                )

        return self.source_reader.load_and_split(self.text_splitter)

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
