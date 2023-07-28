#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import sys
import traceback

sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from pilot.embedding_engine.knowledge_type import KnowledgeType
from pilot.server.knowledge.service import KnowledgeService
from pilot.server.knowledge.request.request import KnowledgeSpaceRequest


from pilot.configs.config import Config
from pilot.configs.model_config import (
    DATASETS_DIR,
    LLM_MODEL_CONFIG,
    KNOWLEDGE_UPLOAD_ROOT_PATH,
)
from pilot.embedding_engine.embedding_engine import EmbeddingEngine

knowledge_space_service = KnowledgeService()

CFG = Config()


class LocalKnowledgeInit:
    embeddings: object = None

    def __init__(self, vector_store_config) -> None:
        self.vector_store_config = vector_store_config
        self.model_name = LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL]

    def knowledge_persist(self, file_path: str, skip_wrong_doc: bool = False):
        """knowledge persist"""
        docs = []
        embedding_engine = None
        for root, _, files in os.walk(file_path, topdown=False):
            for file in files:
                filename = os.path.join(root, file)
                ke = EmbeddingEngine(
                    knowledge_source=filename,
                    knowledge_type=KnowledgeType.DOCUMENT.value,
                    model_name=self.model_name,
                    vector_store_config=self.vector_store_config,
                )
                try:
                    embedding_engine = ke.init_knowledge_embedding()
                    doc = ke.read()
                    docs.extend(doc)
                except Exception as e:
                    error_msg = traceback.format_exc()
                    if skip_wrong_doc:
                        print(
                            f"Warning: document file {filename} embedding error, skip it, error message: {error_msg}"
                        )
                    else:
                        raise e
        embedding_engine.index_to_store(docs)
        print(f"""begin create {self.vector_store_config["vector_store_name"]} space""")
        try:
            space = KnowledgeSpaceRequest
            space.name = self.vector_store_config["vector_store_name"]
            space.desc = "knowledge_init.py"
            space.vector_type = CFG.VECTOR_STORE_TYPE
            space.owner = "DB-GPT"
            knowledge_space_service.create_knowledge_space(space)
        except Exception as e:
            if "have already named" in str(e):
                print(f"Warning: you have already named {space.name}")
            else:
                raise e


if __name__ == "__main__":
    # TODO https://github.com/csunny/DB-GPT/issues/354
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--vector_name", type=str, default="default", help="Your vector store name"
    )
    parser.add_argument(
        "--file_path", type=str, default=DATASETS_DIR, help="Your document path"
    )
    parser.add_argument(
        "--skip_wrong_doc", type=bool, default=False, help="Skip wrong document"
    )
    args = parser.parse_args()
    vector_name = args.vector_name
    store_type = CFG.VECTOR_STORE_TYPE
    file_path = args.file_path
    skip_wrong_doc = args.skip_wrong_doc
    vector_store_config = {
        "vector_store_name": vector_name,
        "vector_store_type": CFG.VECTOR_STORE_TYPE,
        "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
    }
    print(vector_store_config)
    kv = LocalKnowledgeInit(vector_store_config=vector_store_config)
    kv.knowledge_persist(file_path=file_path, skip_wrong_doc=skip_wrong_doc)
    print("your knowledge embedding success...")
