#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from pilot.configs.config import Config
from pilot.configs.model_config import (
    DATASETS_DIR,
    LLM_MODEL_CONFIG,
    VECTOR_SEARCH_TOP_K,
)
from pilot.source_embedding.knowledge_embedding import KnowledgeEmbedding

CFG = Config()


class LocalKnowledgeInit:
    embeddings: object = None
    model_name = LLM_MODEL_CONFIG["text2vec"]
    top_k: int = VECTOR_SEARCH_TOP_K

    def __init__(self, vector_store_config) -> None:
        self.vector_store_config = vector_store_config

    def knowledge_persist(self, file_path, append_mode):
        """knowledge persist"""
        kv = KnowledgeEmbedding(
            file_path=file_path,
            model_name=LLM_MODEL_CONFIG["text2vec"],
            vector_store_config=self.vector_store_config,
        )
        vector_store = kv.knowledge_persist_initialization(append_mode)
        return vector_store

    def query(self, q):
        """Query similar doc from Vector"""
        vector_store = self.init_vector_store()
        docs = vector_store.similarity_search_with_score(q, k=self.top_k)
        for doc in docs:
            dc, s = doc
            yield s, dc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vector_name", type=str, default="default")
    parser.add_argument("--append", type=bool, default=False)
    parser.add_argument("--store_type", type=str, default="Chroma")
    args = parser.parse_args()
    vector_name = args.vector_name
    append_mode = args.append
    store_type = CFG.VECTOR_STORE_TYPE
    vector_store_config = {"vector_store_name": vector_name}
    print(vector_store_config)
    kv = LocalKnowledgeInit(vector_store_config=vector_store_config)
    vector_store = kv.knowledge_persist(file_path=DATASETS_DIR, append_mode=append_mode)
    print("your knowledge embedding success...")
