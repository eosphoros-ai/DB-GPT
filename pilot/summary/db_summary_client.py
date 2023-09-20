import json
import uuid

from pilot.common.schema import DBType
from pilot.component import SystemApp
from pilot.configs.config import Config
from pilot.configs.model_config import (
    KNOWLEDGE_UPLOAD_ROOT_PATH,
    EMBEDDING_MODEL_CONFIG,
    LOGDIR,
)
from pilot.scene.base import ChatScene
from pilot.scene.base_chat import BaseChat
from pilot.scene.chat_factory import ChatFactory
from pilot.summary.rdbms_db_summary import RdbmsSummary
from pilot.utils import build_logger

logger = build_logger("db_summary", LOGDIR + "db_summary.log")


CFG = Config()
chat_factory = ChatFactory()


class DBSummaryClient:
    """db summary client, provide db_summary_embedding(put db profile and table profile summary into vector store)
    , get_similar_tables method(get user query related tables info)
    """

    def __init__(self, system_app: SystemApp):
        self.system_app = system_app

    def db_summary_embedding(self, dbname, db_type):
        """put db profile and table profile summary into vector store"""
        from pilot.embedding_engine.string_embedding import StringEmbedding
        from pilot.embedding_engine.embedding_factory import EmbeddingFactory

        db_summary_client = RdbmsSummary(dbname, db_type)
        embedding_factory = self.system_app.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embeddings = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        vector_store_config = {
            "vector_store_name": dbname + "_summary",
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
            "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            "embeddings": embeddings,
        }
        embedding = StringEmbedding(
            file_path=db_summary_client.get_summery(),
            vector_store_config=vector_store_config,
        )
        self.init_db_profile(db_summary_client, dbname, embeddings)
        if not embedding.vector_name_exist():
            if CFG.SUMMARY_CONFIG == "FAST":
                for vector_table_info in db_summary_client.get_summery():
                    embedding = StringEmbedding(
                        vector_table_info,
                        vector_store_config,
                    )
                    embedding.source_embedding()
            else:
                embedding = StringEmbedding(
                    file_path=db_summary_client.get_summery(),
                    vector_store_config=vector_store_config,
                )
                embedding.source_embedding()
            for (
                table_name,
                table_summary,
            ) in db_summary_client.get_table_summary().items():
                table_vector_store_config = {
                    "vector_store_name": dbname + "_" + table_name + "_ts",
                    "vector_store_type": CFG.VECTOR_STORE_TYPE,
                    "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
                    "embeddings": embeddings,
                }
                embedding = StringEmbedding(
                    table_summary,
                    table_vector_store_config,
                )
                embedding.source_embedding()

        logger.info("db summary embedding success")

    def get_db_summary(self, dbname, query, topk):
        from pilot.embedding_engine.embedding_engine import EmbeddingEngine
        from pilot.embedding_engine.embedding_factory import EmbeddingFactory

        vector_store_config = {
            "vector_store_name": dbname + "_profile",
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
            "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
        }
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        knowledge_embedding_client = EmbeddingEngine(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            vector_store_config=vector_store_config,
            embedding_factory=embedding_factory,
        )
        table_docs = knowledge_embedding_client.similar_search(query, topk)
        ans = [d.page_content for d in table_docs]
        return ans

    def get_similar_tables(self, dbname, query, topk):
        """get user query related tables info"""
        from pilot.embedding_engine.embedding_engine import EmbeddingEngine
        from pilot.embedding_engine.embedding_factory import EmbeddingFactory

        vector_store_config = {
            "vector_store_name": dbname + "_summary",
            "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
            "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
        }
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        knowledge_embedding_client = EmbeddingEngine(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            vector_store_config=vector_store_config,
            embedding_factory=embedding_factory,
        )
        if CFG.SUMMARY_CONFIG == "FAST":
            table_docs = knowledge_embedding_client.similar_search(query, topk)
            related_tables = [
                json.loads(table_doc.page_content)["table_name"]
                for table_doc in table_docs
            ]
        else:
            table_docs = knowledge_embedding_client.similar_search(query, 1)
            # prompt = KnownLedgeBaseQA.build_db_summary_prompt(
            #     query, table_docs[0].page_content
            # )
            related_tables = _get_llm_response(
                query, dbname, table_docs[0].page_content
            )
        related_table_summaries = []
        for table in related_tables:
            vector_store_config = {
                "vector_store_name": dbname + "_" + table + "_ts",
                "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
                "vector_store_type": CFG.VECTOR_STORE_TYPE,
                "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            }
            knowledge_embedding_client = EmbeddingEngine(
                model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                vector_store_config=vector_store_config,
                embedding_factory=embedding_factory,
            )
            table_summery = knowledge_embedding_client.similar_search(query, 1)
            related_table_summaries.append(table_summery[0].page_content)
        return related_table_summaries

    def init_db_summary(self):
        db_mange = CFG.LOCAL_DB_MANAGE
        dbs = db_mange.get_db_list()
        for item in dbs:
            try:
                self.db_summary_embedding(item["db_name"], item["db_type"])
            except Exception as e:
                logger.warn(
                    f'{item["db_name"]}, {item["db_type"]} summary error!{str(e)}', e
                )

    def init_db_profile(self, db_summary_client, dbname, embeddings):
        from pilot.embedding_engine.string_embedding import StringEmbedding

        vector_store_name = dbname + "_profile"
        profile_store_config = {
            "vector_store_name": vector_store_name,
            "chroma_persist_path": KNOWLEDGE_UPLOAD_ROOT_PATH,
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
            "embeddings": embeddings,
        }
        embedding = StringEmbedding(
            file_path=db_summary_client.get_db_summery(),
            vector_store_config=profile_store_config,
        )
        if not embedding.vector_name_exist():
            docs = []
            docs.extend(embedding.read_batch())
            for table_summary in db_summary_client.table_info_json():
                embedding = StringEmbedding(
                    table_summary,
                    profile_store_config,
                )
                docs.extend(embedding.read_batch())
            embedding.index_to_store(docs)
        else:
            logger.info(f"Vector store name {vector_store_name} exist")
        logger.info("init db profile success...")


def _get_llm_response(query, db_input, dbsummary):
    chat_param = {
        "temperature": 0.7,
        "max_new_tokens": 512,
        "chat_session_id": uuid.uuid1(),
        "user_input": query,
        "db_select": db_input,
        "db_summary": dbsummary,
    }
    chat: BaseChat = chat_factory.get_implementation(
        ChatScene.InnerChatDBSummary.value, **chat_param
    )
    res = chat._blocking_nostream_call()
    return json.loads(res)["table"]
