#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import copy
from typing import Optional, List, Dict
from langchain.prompts import PromptTemplate
from langchain.vectorstores import Chroma 
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import UnstructuredFileLoader, UnstructuredPDFLoader, TextLoader
from langchain.chains import VectorDBQA
from langchain.embeddings import HuggingFaceEmbeddings
from pilot.configs.model_config import VECTORE_PATH, DATASETS_DIR, LLM_MODEL_CONFIG

VECTOR_SEARCH_TOP_K = 5

class KnownLedge2Vector:

    embeddings: object = None 
    model_name = LLM_MODEL_CONFIG["sentence-transforms"]
    top_k: int = VECTOR_SEARCH_TOP_K

    def __init__(self, model_name=None) -> None:
        if not model_name:
            # use default embedding model
            self.embeddings = HuggingFaceEmbeddings(model_name=self.model_name) 
        
    def init_vector_store(self):
        documents = self.load_knownlege()
        persist_dir = os.path.join(VECTORE_PATH, ".vectordb")
        print("向量数据库持久化地址: ", persist_dir)
        if os.path.exists(persist_dir):
            # 从本地持久化文件中Load
            vector_store = Chroma(persist_directory=persist_dir, embedding_function=self.embeddings)
            vector_store.add_documents(documents=documents)
        else:
            # 重新初始化
            vector_store = Chroma.from_documents(documents=documents, 
                                                 embedding=self.embeddings,
                                                 persist_directory=persist_dir)
            vector_store.persist()
            vector_store = None 
        return persist_dir

    def load_knownlege(self):
        docments = []
        for root, _, files in os.walk(DATASETS_DIR, topdown=False):
            for file in files:
                filename = os.path.join(root, file)
                docs = self._load_file(filename)
                # 更新metadata数据
                new_docs = [] 
                for doc in docs:
                    doc.metadata = {"source": doc.metadata["source"].replace(DATASETS_DIR, "")} 
                    print("文档2向量初始化中, 请稍等...", doc.metadata)
                    new_docs.append(doc)
                docments += new_docs
        return docments

    def _load_file(self, filename):
        # 加载文件
        if filename.lower().endswith(".pdf"):
            loader = UnstructuredFileLoader(filename) 
            text_splitor = CharacterTextSplitter()
            docs = loader.load_and_split(text_splitor)
        else:
            loader = UnstructuredFileLoader(filename, mode="elements")
            text_splitor = CharacterTextSplitter()
            docs = loader.load_and_split(text_splitor)
        return docs

    def _load_from_url(self, url):
        pass


if __name__ == "__main__":
    k2v = KnownLedge2Vector()
    k2v.init_vector_store()
            