#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from abc import ABC, abstractmethod

from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma

from typing import List, Optional, Dict

registered_methods = []


def register(method):
    registered_methods.append(method.__name__)
    return method


class SourceEmbedding(ABC):
    """base class for read data source embedding pipeline.
    include data read, data process, data split, data to vector, data index vector store
    Implementations should implement the  method
    """

    def __init__(self, file_path, model_name, vector_store_config, embedding_args: Optional[Dict] = None):
        """Initialize with Loader url, model_name, vector_store_config"""
        self.file_path = file_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config
        self.embedding_args = embedding_args
        self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name)
        persist_dir = os.path.join(self.vector_store_config["vector_store_path"],
                                   self.vector_store_config["vector_store_name"] + ".vectordb")
        self.vector_store_client = Chroma(persist_directory=persist_dir, embedding_function=self.embeddings)

    @abstractmethod
    @register
    def read(self) -> List[ABC]:
        """read datasource into document objects."""
    @register
    def data_process(self, text):
        """pre process data."""

    @register
    def text_split(self, text):
        """text split chunk"""
        pass

    @register
    def text_to_vector(self, docs):
        """transform vector"""
        pass

    @register
    def index_to_store(self, docs):
        """index to vector store"""
        persist_dir = os.path.join(self.vector_store_config["vector_store_path"],
                                   self.vector_store_config["vector_store_name"] + ".vectordb")
        self.vector_store = Chroma.from_documents(docs, self.embeddings, persist_directory=persist_dir)
        self.vector_store.persist()

    @register
    def similar_search(self, doc, topk):
        """vector store similarity_search"""

        return self.vector_store_client.similarity_search(doc, topk)

    def source_embedding(self):
        if 'read' in registered_methods:
            text = self.read()
        if 'data_process' in registered_methods:
            text = self.data_process(text)
        if 'text_split' in registered_methods:
            self.text_split(text)
        if 'text_to_vector' in registered_methods:
            self.text_to_vector(text)
        if 'index_to_store' in registered_methods:
            self.index_to_store(text)

    def batch_embedding(self):
        if 'read_batch' in registered_methods:
            text = self.read_batch()
        if 'data_process' in registered_methods:
            text = self.data_process(text)
        if 'text_split' in registered_methods:
            self.text_split(text)
        if 'text_to_vector' in registered_methods:
            self.text_to_vector(text)
        if 'index_to_store' in registered_methods:
            self.index_to_store(text)
