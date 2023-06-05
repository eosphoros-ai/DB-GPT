#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from typing import List

import markdown
from bs4 import BeautifulSoup
from langchain.document_loaders import TextLoader
from langchain.schema import Document

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
        text_splitter = CHNDocumentSplitter(
            pdf=True, sentence_size=CFG.KNOWLEDGE_CHUNK_SIZE
        )
        return loader.load_and_split(text_splitter)

    @register
    def read_batch(self):
        """Load from markdown path."""
        docments = []
        for root, _, files in os.walk(self.file_path, topdown=False):
            for file in files:
                filename = os.path.join(root, file)
                loader = TextLoader(filename)
                # text_splitor = CHNDocumentSplitter(chunk_size=1000, chunk_overlap=20, length_function=len)
                # docs = loader.load_and_split()
                docs = loader.load()
                # 更新metadata数据
                new_docs = []
                for doc in docs:
                    doc.metadata = {
                        "source": doc.metadata["source"].replace(self.file_path, "")
                    }
                    print("doc is embedding ... ", doc.metadata)
                    new_docs.append(doc)
                docments += new_docs
        return docments

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
