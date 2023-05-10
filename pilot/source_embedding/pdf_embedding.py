#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os

from bs4 import BeautifulSoup
from langchain.document_loaders import UnstructuredFileLoader, UnstructuredPDFLoader
from langchain.vectorstores import Milvus, Chroma
from pymilvus import connections

from pilot.server.vicuna_server import embeddings
from pilot.source_embedding.text_to_vector import TextToVector
# from vector_store import ESVectorStore

from pilot.source_embedding import SourceEmbedding, register


class PDFEmbedding(SourceEmbedding):
    """yuque embedding for read yuque document."""

    def __init__(self, file_path, model_name, vector_store_config):
        """Initialize with YuqueLoader url."""
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config

    @register
    def read(self):
        """Load from pdf path."""
        docs = []
        # loader = UnstructuredFileLoader(self.file_path)
        loader = UnstructuredPDFLoader(self.file_path, mode="elements")
        return loader.load()[0]

    @register
    def text_to_vector(self, docs):
        """Load from yuque url."""
        for doc in docs:
            doc["vector"] = TextToVector.textToVector(doc["content"])[0]
        return docs

    @register
    def index_to_store(self, docs):
        """index into vector store."""

        # vector_db = Milvus.add_texts(
        #     docs,
        #     embeddings,
        #     connection_args={"host": "127.0.0.1", "port": "19530"},
        # )
        db = Chroma.from_documents(docs, embeddings)

        return Chroma.from_documents(docs, embeddings)

