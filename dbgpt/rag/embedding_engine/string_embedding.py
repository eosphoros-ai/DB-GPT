from typing import List, Optional

from langchain.schema import Document
from langchain.text_splitter import (
    TextSplitter,
    SpacyTextSplitter,
    RecursiveCharacterTextSplitter,
)

from dbgpt.rag.embedding_engine import SourceEmbedding, register


class StringEmbedding(SourceEmbedding):
    """string embedding for read string document."""

    def __init__(
        self,
        file_path,
        vector_store_config,
        source_reader: Optional = None,
        text_splitter: Optional[TextSplitter] = None,
    ):
        """Initialize raw text word path.
        Args:
           - file_path: data source path
           - vector_store_config: vector store config params.
           - source_reader: Optional[BaseLoader]
           - text_splitter: Optional[TextSplitter]
        """
        super().__init__(
            file_path=file_path,
            vector_store_config=vector_store_config,
            source_reader=None,
            text_splitter=None,
        )
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.source_reader = source_reader or None
        self.text_splitter = text_splitter or None

    @register
    def read(self):
        """Load from String path."""
        metadata = {"source": "raw text"}
        docs = [Document(page_content=self.file_path, metadata=metadata)]
        if self.text_splitter is None:
            try:
                self.text_splitter = SpacyTextSplitter(
                    pipeline="zh_core_web_sm",
                    chunk_size=500,
                    chunk_overlap=100,
                )
            except Exception:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=500, chunk_overlap=100
                )
            return self.text_splitter.split_documents(docs)
        return docs

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            documents[i].page_content = d.page_content.replace("\n", "")
            i += 1
        return documents
