#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse

from pilot.configs.model_config import DATASETS_DIR, LLM_MODEL_CONFIG, VECTOR_SEARCH_TOP_K, \
    KNOWLEDGE_UPLOAD_ROOT_PATH
from pilot.source_embedding.knowledge_embedding import KnowledgeEmbedding


class LocalKnowledgeInit:
    embeddings: object = None
    model_name = LLM_MODEL_CONFIG["text2vec"]
    top_k: int = VECTOR_SEARCH_TOP_K

    def __init__(self) -> None:
        pass

    def knowledge_persist(self, file_path, vector_name, append_mode):
        """ knowledge persist """
        kv = KnowledgeEmbedding(
            file_path=file_path,
            model_name=LLM_MODEL_CONFIG["text2vec"],
            vector_store_config= {"vector_store_name":vector_name, "vector_store_path": KNOWLEDGE_UPLOAD_ROOT_PATH})
        vector_store = kv.knowledge_persist_initialization(append_mode)
        return vector_store

    def query(self, q):
        """Query similar doc from Vector """
        vector_store = self.init_vector_store()
        docs = vector_store.similarity_search_with_score(q, k=self.top_k)
        for doc in docs:
            dc, s = doc
            yield s, dc

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vector_name", type=str, default="default")
    parser.add_argument("--append", type=bool, default=False)
    args = parser.parse_args()
    vector_name = args.vector_name
    append_mode = args.append
    kv  = LocalKnowledgeInit()
    vector_store = kv.knowledge_persist(file_path=DATASETS_DIR, vector_name=vector_name, append_mode=append_mode)
    print("your knowledge embedding success...")