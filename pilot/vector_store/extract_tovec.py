#!/usr/bin/env python3
# -*- coding:utf-8 -*-


from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma
from pilot.model.vicuna_llm import VicunaEmbeddingLLM

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



