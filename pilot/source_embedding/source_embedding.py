#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod

from pymilvus import connections, FieldSchema, DataType, CollectionSchema

from pilot.source_embedding.text_to_vector import TextToVector

from typing import List


registered_methods = []


def register(method):
    registered_methods.append(method.__name__)
    return method


class SourceEmbedding(ABC):
    """base class for read data source embedding pipeline.
    include data read, data process, data split, data to vector, data index vector store
    Implementations should implement the  method
    """

    def __init__(self, yuque_path, model_name, vector_store_config):
        """Initialize with YuqueLoader url, model_name, vector_store_config"""
        self.yuque_path = yuque_path
        self.model_name = model_name
        self.vector_store_config = vector_store_config

    # Sub-classes should implement this method
    # as return list(self.lazy_load()).
    # This method returns a List which is materialized in memory.
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
        for doc in docs:
            doc["vector"] = TextToVector.textToVector(doc["content"])[0]
        return docs

    @register
    def index_to_store(self):
        """index to vector store"""
        milvus = connections.connect(
            alias="default",
            host='localhost',
            port="19530"
        )
        doc_id = FieldSchema(
            name="doc_id",
            dtype=DataType.INT64,
            is_primary=True,
        )
        doc_vector = FieldSchema(
            name="doc_vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=self.vector_store_config["dim"]
        )
        schema = CollectionSchema(
            fields=[doc_id, doc_vector],
            description=self.vector_store_config["description"]
        )

    @register
    def index_to_store(self):
        """index to vector store"""
        milvus = connections.connect(
            alias="default",
            host='localhost',
            port="19530"
        )
        doc_id = FieldSchema(
            name="doc_id",
            dtype=DataType.INT64,
            is_primary=True,
        )
        doc_vector = FieldSchema(
            name="doc_vector",
            dtype=DataType.FLOAT_VECTOR,
            dim=self.vector_store_config["dim"]
        )
        schema = CollectionSchema(
            fields=[doc_id, doc_vector],
            description=self.vector_store_config["description"]
        )

    def source_embedding(self):
        if 'read' in registered_methods:
            text = self.read()
        if 'process' in registered_methods:
            self.process(text)
        if 'text_split' in registered_methods:
            self.text_split(text)
        if 'text_to_vector' in registered_methods:
            self.text_to_vector(text)
        if 'index_to_store' in registered_methods:
            self.index_to_store(text)
