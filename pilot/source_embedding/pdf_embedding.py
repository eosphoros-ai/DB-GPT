#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List

from langchain.document_loaders import PyPDFLoader
from langchain.schema import Document

from pilot.configs.model_config import KNOWLEDGE_CHUNK_SPLIT_SIZE
from pilot.source_embedding import SourceEmbedding, register
from pilot.source_embedding.chn_document_splitter import CHNDocumentSplitter


class PDFEmbedding(SourceEmbedding):
    """yuque embedding for read yuque document."""

    def __init__(self, file_path, model_name, vector_store_config):
        """Initialize with pdf path."""
        super().__init__(file_path, model_name, vector_store_config)
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config

    @register
    def read(self):
        """Load from pdf path."""
        # loader = UnstructuredPaddlePDFLoader(self.file_path)
        loader = PyPDFLoader(self.file_path)
        textsplitter = CHNDocumentSplitter(
            pdf=True, sentence_size=KNOWLEDGE_CHUNK_SPLIT_SIZE
        )
        return loader.load_and_split(textsplitter)

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            documents[i].page_content = d.page_content.replace("\n", "")
            i += 1
        return documents
