import json
import uuid

from langchain.embeddings import HuggingFaceEmbeddings, logger

from pilot.configs.config import Config
from pilot.configs.model_config import LLM_MODEL_CONFIG
from pilot.scene.base import ChatScene
from pilot.scene.base_chat import BaseChat
from pilot.source_embedding.knowledge_embedding import KnowledgeEmbedding
from pilot.source_embedding.string_embedding import StringEmbedding
from pilot.summary.mysql_db_summary import MysqlSummary
from pilot.scene.chat_factory import ChatFactory

CFG = Config()
chat_factory = ChatFactory()


class DBSummaryClient:
    """db summary client, provide db_summary_embedding(put db profile and table profile summary into vector store)
    , get_similar_tables method(get user query related tables info)
    """

    @staticmethod
    def db_summary_embedding(dbname):
        """put db profile and table profile summary into vector store"""
        if CFG.LOCAL_DB_HOST is not None and CFG.LOCAL_DB_PORT is not None:
            db_summary_client = MysqlSummary(dbname)
        embeddings = HuggingFaceEmbeddings(
            model_name=LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        vector_store_config = {
            "vector_store_name": dbname + "_profile",
            "embeddings": embeddings,
        }
        embedding = StringEmbedding(
            db_summary_client.get_summery(),
            LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            vector_store_config,
        )
        if not embedding.vector_name_exist():
            if CFG.SUMMARY_CONFIG == "FAST":
                for vector_table_info in db_summary_client.get_summery():
                    embedding = StringEmbedding(
                        vector_table_info,
                        LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                        vector_store_config,
                    )
                    embedding.source_embedding()
            else:
                embedding = StringEmbedding(
                    db_summary_client.get_summery(),
                    LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                    vector_store_config,
                )
                embedding.source_embedding()
            for (
                table_name,
                table_summary,
            ) in db_summary_client.get_table_summary().items():
                table_vector_store_config = {
                    "vector_store_name": table_name + "_ts",
                    "embeddings": embeddings,
                }
                embedding = StringEmbedding(
                    table_summary,
                    LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                    table_vector_store_config,
                )
                embedding.source_embedding()

        logger.info("db summary embedding success")

    @staticmethod
    def get_similar_tables(dbname, query, topk):
        """get user query related tables info"""
        embeddings = HuggingFaceEmbeddings(
            model_name=LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        vector_store_config = {
            "vector_store_name": dbname + "_profile",
            "embeddings": embeddings,
        }
        knowledge_embedding_client = KnowledgeEmbedding(
            file_path="",
            model_name=LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
            local_persist=False,
            vector_store_config=vector_store_config,
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
                "vector_store_name": table + "_ts",
                "embeddings": embeddings,
            }
            knowledge_embedding_client = KnowledgeEmbedding(
                file_path="",
                model_name=LLM_MODEL_CONFIG[CFG.EMBEDDING_MODEL],
                local_persist=False,
                vector_store_config=vector_store_config,
            )
            table_summery = knowledge_embedding_client.similar_search(query, 1)
            related_table_summaries.append(table_summery[0].page_content)
        return related_table_summaries


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
    res = chat.nostream_call()
    return json.loads(res)["table"]


# if __name__ == "__main__":
#     # summary = DBSummaryClient.get_similar_tables("db_test", "查询在线用户的购物车", 10)
#
#     text= """Based on the input "查询在线聊天的用户好友" and the known database information, the tables involved in the user input are "chat_users" and "friends".
# Response:
#
# {
#    "table": ["chat_users"]
# }"""
#     text = text.rstrip().replace("\n","")
#     start = text.find("{")
#     end = text.find("}") + 1
#
#     # 从字符串中截取出JSON数据
#     json_str = text[start:end]
#
#     # 将JSON数据转换为Python中的字典类型
#     data = json.loads(json_str)
#     # pattern = r'{s*"table"s*:s*[[^]]*]s*}'
#     # match = re.search(pattern, text)
#     # if match:
#     #     json_string = match.group(0)
#     #     # 将JSON字符串转换为Python对象
#     #     json_obj = json.loads(json_string)
#     # print(summary)
