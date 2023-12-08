import logging

from dbgpt.component import SystemApp
from dbgpt._private.config import Config
from dbgpt.configs.model_config import (
    EMBEDDING_MODEL_CONFIG,
)

from dbgpt.rag.summary.rdbms_db_summary import RdbmsSummary

logger = logging.getLogger(__name__)

CFG = Config()


class DBSummaryClient:
    """DB Summary client, provide db_summary_embedding(put db profile and table profile summary into vector store)
    , get_similar_tables method(get user query related tables info)
    Args:
        system_app (SystemApp): Main System Application class that manages the lifecycle and registration of components..
    """

    def __init__(self, system_app: SystemApp):
        self.system_app = system_app

    def db_summary_embedding(self, dbname, db_type):
        """put db profile and table profile summary into vector store"""
        from dbgpt.rag.embedding_engine.embedding_factory import EmbeddingFactory

        db_summary_client = RdbmsSummary(dbname, db_type)
        embedding_factory = self.system_app.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embeddings = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        self.init_db_profile(db_summary_client, dbname, embeddings)

        logger.info("db summary embedding success")

    def get_db_summary(self, dbname, query, topk):
        """get user query related tables info"""
        from dbgpt.rag.embedding_engine.embedding_engine import EmbeddingEngine
        from dbgpt.rag.embedding_engine.embedding_factory import EmbeddingFactory

        vector_store_config = {
            "vector_store_name": dbname + "_profile",
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
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

    def init_db_summary(self):
        """init db summary"""
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
        """db profile initialization
        Args:
        db_summary_client(DBSummaryClient): DB Summary Client
        dbname(str): dbname
        embeddings(SourceEmbedding): embedding for read string document
        """
        from dbgpt.rag.embedding_engine.string_embedding import StringEmbedding

        vector_store_name = dbname + "_profile"
        profile_store_config = {
            "vector_store_name": vector_store_name,
            "vector_store_type": CFG.VECTOR_STORE_TYPE,
            "embeddings": embeddings,
        }
        embedding = StringEmbedding(
            file_path=None,
            vector_store_config=profile_store_config,
        )
        if not embedding.vector_name_exist():
            docs = []
            for table_summary in db_summary_client.table_summaries():
                from langchain.text_splitter import RecursiveCharacterTextSplitter

                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=len(table_summary), chunk_overlap=0
                )
                embedding = StringEmbedding(
                    file_path=table_summary,
                    vector_store_config=profile_store_config,
                    text_splitter=text_splitter,
                )
                docs.extend(embedding.read_batch())
            if len(docs) > 0:
                embedding.index_to_store(docs)
        else:
            logger.info(f"Vector store name {vector_store_name} exist")
        logger.info("initialize db summary profile success...")
