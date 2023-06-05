#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List

from langchain.document_loaders import PyPDFLoader
from langchain.schema import Document

from pilot.configs.config import Config
from pilot.source_embedding import SourceEmbedding, register
from pilot.source_embedding.chn_document_splitter import CHNDocumentSplitter

CFG = Config()


class PDFEmbedding(SourceEmbedding):
    """pdf embedding for read pdf document."""

    def __init__(self, file_path, vector_store_config, encoding):
        """Initialize with pdf path."""
        super().__init__(file_path, vector_store_config)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.encoding = encoding

    @register
    def read(self):
        """Load from pdf path."""
        # loader = UnstructuredPaddlePDFLoader(self.file_path)
        loader = PyPDFLoader(self.file_path)
        textsplitter = CHNDocumentSplitter(
            pdf=True, sentence_size=CFG.KNOWLEDGE_CHUNK_SIZE
        )
        return loader.load_and_split(textsplitter)

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            documents[i].page_content = d.page_content.replace("\n", "")
            i += 1
        return documents
