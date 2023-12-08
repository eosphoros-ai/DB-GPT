#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List, Optional

import markdown
from bs4 import BeautifulSoup
from langchain.schema import Document
from langchain.text_splitter import (
    SpacyTextSplitter,
    CharacterTextSplitter,
    RecursiveCharacterTextSplitter,
    TextSplitter,
)

from dbgpt.rag.embedding_engine import SourceEmbedding, register
from dbgpt.rag.embedding_engine.encode_text_loader import EncodeTextLoader


class MarkdownEmbedding(SourceEmbedding):
    """markdown embedding for read markdown document."""

    def __init__(
        self,
        file_path,
        vector_store_config,
        source_reader: Optional = None,
        text_splitter: Optional[TextSplitter] = None,
    ):
        """Initialize raw text word path."""
        super().__init__(
            file_path, vector_store_config, source_reader=None, text_splitter=None
        )
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.source_reader = source_reader or None
        self.text_splitter = text_splitter or None

    @register
    def read(self):
        """Load from markdown path."""
        if self.source_reader is None:
            self.source_reader = EncodeTextLoader(self.file_path)
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
            content = markdown.markdown(d.page_content)
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup(["!doctype", "meta", "i.fa"]):
                tag.extract()
            documents[i].page_content = soup.get_text()
            documents[i].page_content = documents[i].page_content.replace("\n", " ")
            i += 1
        return documents
