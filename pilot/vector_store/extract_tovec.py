#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import os

from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from pilot.model.vicuna_llm import VicunaEmbeddingLLM
from pilot.configs.model_config import VECTORE_PATH
from langchain.embeddings import HuggingFaceEmbeddings

embeddings = VicunaEmbeddingLLM()

def knownledge_tovec(filename):
    with open(filename, "r") as f:
        knownledge = f.read()
    
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_text(knownledge)
    docsearch = Chroma.from_texts(
        texts, embeddings, metadatas=[{"source": str(i)} for i in range(len(texts))]
    )
    return docsearch

def knownledge_tovec_st(filename):
    """ Use sentence transformers to embedding the document.
        https://github.com/UKPLab/sentence-transformers
    """
    from pilot.configs.model_config import llm_model_config
    embeddings = HuggingFaceEmbeddings(model=llm_model_config["sentence-transforms"])

    with open(filename, "r") as f:
        knownledge = f.read()
    
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter(knownledge)
    docsearch = Chroma.from_texts(texts, embeddings, metadatas=[{"source": str(i)} for i in range(len(texts))])
    return docsearch

def get_vector_storelist():
    if not os.path.exists(VECTORE_PATH):
        return []
    return os.listdir(VECTORE_PATH)