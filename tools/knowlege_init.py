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
)
from pilot.source_embedding.knowledge_embedding import KnowledgeEmbedding

CFG = Config()


class LocalKnowledgeInit:
    embeddings: object = None

    def __init__(self, vector_store_config) -> None:
        self.vector_store_config = vector_store_config
        self.model_name = LLM_MODEL_CONFIG["text2vec"]

    def knowledge_persist(self, file_path):
        """knowledge persist"""
        for root, _, files in os.walk(file_path, topdown=False):
            for file in files:
                filename = os.path.join(root, file)
                # docs = self._load_file(filename)
                ke = KnowledgeEmbedding(
                    file_path=filename,
                    model_name=self.model_name,
                    vector_store_config=self.vector_store_config,
                )
                client = ke.init_knowledge_embedding()
                client.source_embedding()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--vector_name", type=str, default="default")
    args = parser.parse_args()
    vector_name = args.vector_name
    store_type = CFG.VECTOR_STORE_TYPE
    vector_store_config = {"vector_store_name": vector_name}
    print(vector_store_config)
    kv = LocalKnowledgeInit(vector_store_config=vector_store_config)
    kv.knowledge_persist(file_path=DATASETS_DIR)
    print("your knowledge embedding success...")
