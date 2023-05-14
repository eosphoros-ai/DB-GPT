#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List

from langchain.document_loaders import PyPDFLoader
from langchain.schema import Document

from pilot.source_embedding import SourceEmbedding, register


class PDFEmbedding(SourceEmbedding):
    """yuque embedding for read yuque document."""

    def __init__(self, file_path, model_name, vector_store_config):
        """Initialize with pdf path."""
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config

    @register
    def read(self):
        """Load from pdf path."""
        loader = PyPDFLoader(self.file_path)
        return loader.load()

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            documents[i].page_content = d.page_content.replace(" ", "").replace("\n", "")
            i += 1
        return documents



