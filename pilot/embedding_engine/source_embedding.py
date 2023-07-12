#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from chromadb.errors import NotEnoughElementsException
from langchain.text_splitter import TextSplitter

from pilot.vector_store.connector import VectorStoreConnector

registered_methods = []


def register(method):
    registered_methods.append(method.__name__)
    return method


class SourceEmbedding(ABC):
    """base class for read data source embedding pipeline.
    include data read, data process, data split, data to vector, data index vector store
    Implementations should implement the  method
    """

    def __init__(
        self,
        file_path,
        vector_store_config: {},
        text_splitter: Optional[TextSplitter] = None,
        embedding_args: Optional[Dict] = None,
    ):
        """Initialize with Loader url, model_name, vector_store_config"""
        self.file_path = file_path
        self.vector_store_config = vector_store_config
        self.text_splitter = text_splitter or None
        self.embedding_args = embedding_args
        self.embeddings = vector_store_config["embeddings"]

    @abstractmethod
    @register
    def read(self) -> List[ABC]:
        """read datasource into document objects."""

    @register
    def data_process(self, text):
        """pre process data."""

    @register
    def text_splitter(self, text_splitter: TextSplitter):
        """add text split chunk"""
        pass

    @register
    def text_to_vector(self, docs):
        """transform vector"""
        pass

    @register
    def index_to_store(self, docs):
        """index to vector store"""
        self.vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        return self.vector_client.load_document(docs)

    @register
    def similar_search(self, doc, topk):
        """vector store similarity_search"""
        self.vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        try:
            ans = self.vector_client.similar_search(doc, topk)
        except NotEnoughElementsException:
            ans = self.vector_client.similar_search(doc, 1)
        return ans

    def vector_name_exist(self):
        self.vector_client = VectorStoreConnector(
            self.vector_store_config["vector_store_type"], self.vector_store_config
        )
        return self.vector_client.vector_name_exists()

    def source_embedding(self):
        if "read" in registered_methods:
            text = self.read()
        if "data_process" in registered_methods:
            text = self.data_process(text)
        if "text_split" in registered_methods:
            self.text_split(text)
        if "text_to_vector" in registered_methods:
            self.text_to_vector(text)
        if "index_to_store" in registered_methods:
            self.index_to_store(text)

    def read_batch(self):
        if "read" in registered_methods:
            text = self.read()
        if "data_process" in registered_methods:
            text = self.data_process(text)
        if "text_split" in registered_methods:
            self.text_split(text)
        return text
