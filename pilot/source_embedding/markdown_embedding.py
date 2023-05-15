#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List

from bs4 import BeautifulSoup
from langchain.document_loaders import TextLoader
from langchain.schema import Document
import markdown

from pilot.source_embedding import SourceEmbedding, register


class MarkdownEmbedding(SourceEmbedding):
    """markdown embedding for read markdown document."""

    def __init__(self, file_path, model_name, vector_store_config):
        """Initialize with markdown path."""
        super().__init__(file_path, model_name, vector_store_config)
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config

    @register
    def read(self):
        """Load from markdown path."""
        loader = TextLoader(self.file_path)
        return loader.load()

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            content = markdown.markdown(d.page_content)
            soup = BeautifulSoup(content, 'html.parser')
            for tag in soup(['!doctype', 'meta', 'i.fa']):
                tag.extract()
            documents[i].page_content = soup.get_text()
            documents[i].page_content = documents[i].page_content.replace(" ", "").replace("\n", " ")
            i += 1
        return documents



