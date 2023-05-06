#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from langchain.prompts import PromptTemplate
from langchain.vectorstores import Chroma 
from langchain.text_splitter import CharacterTextSplitter
from langchain.document_loaders import UnstructuredFileLoader, UnstructuredPDFLoader

VECTOR_SEARCH_TOP_K = 5

class BaseKnownLedgeQA:
    
    llm: object = None
    embeddings: object = None

    top_k: int = VECTOR_SEARCH_TOP_K

    def __init__(self) -> None:
        pass
        
    def init_vector_store(self):
        pass

    def load_knownlege(self):
        pass

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
            