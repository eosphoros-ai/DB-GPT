#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from typing import List

import markdown
from bs4 import BeautifulSoup
from langchain.schema import Document
from langchain.text_splitter import (
    SpacyTextSplitter,
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
)

from pilot.embedding_engine import SourceEmbedding, register
from pilot.embedding_engine.EncodeTextLoader import EncodeTextLoader


class MarkdownEmbedding(SourceEmbedding):
    """markdown embedding for read markdown document."""

    def __init__(self, file_path, vector_store_config, text_splitter=None):
        """Initialize raw text word path."""
        super().__init__(file_path, vector_store_config, text_splitter=None)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.text_splitter = text_splitter or None
        # self.encoding = encoding

    @register
    def read(self):
        """Load from markdown path."""
        loader = EncodeTextLoader(self.file_path)
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

        return loader.load_and_split(self.text_splitter)

    @register
    def data_process(self, documents: List[Document]):
        i = 0
        for d in documents:
            content = markdown.markdown(d.page_content)
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["!doctype", "meta", "i.fa"]):
                tag.extract()
            documents[i].page_content = soup.get_text()
            documents[i].page_content = documents[i].page_content.replace("\n", " ")
            i += 1
        return documents
