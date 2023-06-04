#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import os

from langchain.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma

from pilot.configs.model_config import DATASETS_DIR, VECTORE_PATH
from pilot.model.llm_out.vicuna_llm import VicunaEmbeddingLLM

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
    """Use sentence transformers to embedding the document.
    https://github.com/UKPLab/sentence-transformers
    """
    from pilot.configs.model_config import LLM_MODEL_CONFIG

    embeddings = HuggingFaceEmbeddings(
        model_name=LLM_MODEL_CONFIG["sentence-transforms"]
    )

    with open(filename, "r") as f:
        knownledge = f.read()

    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)

    texts = text_splitter.split_text(knownledge)
    docsearch = Chroma.from_texts(
        texts, embeddings, metadatas=[{"source": str(i)} for i in range(len(texts))]
    )
    return docsearch


def load_knownledge_from_doc():
    """Loader Knownledge from current datasets
    # TODO if the vector store is exists, just use it.
    """

    if not os.path.exists(DATASETS_DIR):
        print(
            "Not Exists Local DataSets, We will answers the Question use model default."
        )

    from pilot.configs.model_config import LLM_MODEL_CONFIG

    embeddings = HuggingFaceEmbeddings(
        model_name=LLM_MODEL_CONFIG["sentence-transforms"]
    )

    files = os.listdir(DATASETS_DIR)
    for file in files:
        if not os.path.isdir(file):
            filename = os.path.join(DATASETS_DIR, file)
            with open(filename, "r") as f:
                knownledge = f.read()

    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_owerlap=0)
    texts = text_splitter.split_text(knownledge)
    docsearch = Chroma.from_texts(
        texts,
        embeddings,
        metadatas=[{"source": str(i)} for i in range(len(texts))],
        persist_directory=os.path.join(VECTORE_PATH, ".vectore"),
    )
    return docsearch


def get_vector_storelist():
    if not os.path.exists(VECTORE_PATH):
        return []
    return os.listdir(VECTORE_PATH)
