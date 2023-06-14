#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from typing import List

import markdown
from bs4 import BeautifulSoup
from langchain.schema import Document
from langchain.text_splitter import SpacyTextSplitter

from pilot.configs.config import Config
from pilot.source_embedding import SourceEmbedding, register
from pilot.source_embedding.EncodeTextLoader import EncodeTextLoader
from pilot.source_embedding.chn_document_splitter import CHNDocumentSplitter

CFG = Config()


class MarkdownEmbedding(SourceEmbedding):
    """markdown embedding for read markdown document."""

    def __init__(self, file_path, vector_store_config):
        """Initialize with markdown path."""
        super().__init__(file_path, vector_store_config)
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        # self.encoding = encoding

    @register
    def read(self):
        """Load from markdown path."""
        loader = EncodeTextLoader(self.file_path)
        textsplitter = SpacyTextSplitter(
            pipeline="zh_core_web_sm",
            chunk_size=CFG.KNOWLEDGE_CHUNK_SIZE,
            chunk_overlap=100,
        )
        return loader.load_and_split(textsplitter)

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
