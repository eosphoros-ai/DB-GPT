#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys

from pilot.embedding_engine.knowledge_type import KnowledgeType
from pilot.openapi.knowledge.knowledge_service import KnowledgeService
from pilot.openapi.knowledge.request.knowledge_request import KnowledgeSpaceRequest

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from pilot.configs.config import Config
from pilot.configs.model_config import (
    DATASETS_DIR,
    LLM_MODEL_CONFIG,
)
from pilot.embedding_engine.knowledge_embedding import KnowledgeEmbedding
knowledge_space_service = KnowledgeService()

CFG = Config()


class LocalKnowledgeInit:
    embeddings: object = None

    def __init__(self, vector_store_config) -> None:
        self.vector_store_config = vector_store_config
        self.model_name = LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL]

    def knowledge_persist(self, file_path):
        """knowledge persist"""
        docs = []
        embedding_engine = None
        for root, _, files in os.walk(file_path, topdown=False):
            for file in files:
                filename = os.path.join(root, file)
                ke = KnowledgeEmbedding(
                    knowledge_source=filename,
                    knowledge_type=KnowledgeType.DOCUMENT.value,
                    model_name=self.model_name,
                    vector_store_config=self.vector_store_config,
                )
                embedding_engine = ke.init_knowledge_embedding()
                doc = ke.read()
                docs.extend(doc)
        embedding_engine.index_to_store(docs)
        print(f"""begin create {self.vector_store_config["vector_store_name"]} space""")
        space = KnowledgeSpaceRequest
        space.name = self.vector_store_config["vector_store_name"]
        space.desc = "knowledge_init.py"
        space.owner = "DB-GPT"
        knowledge_space_service.create_knowledge_space(space)


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
