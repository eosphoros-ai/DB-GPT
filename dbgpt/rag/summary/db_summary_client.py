"""DBSummaryClient class."""

import logging
import traceback

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.rag.summary.gdbms_db_summary import GdbmsSummary
from dbgpt.rag.summary.rdbms_db_summary import RdbmsSummary

logger = logging.getLogger(__name__)

CFG = Config()


class DBSummaryClient:
    """The client for DBSummary.

    DB Summary client, provide db_summary_embedding(put db profile and table profile
    summary into vector store), get_similar_tables method(get user query related tables
    info)

    Args:
        system_app (SystemApp): Main System Application class that manages the
            lifecycle and registration of components..
    """

    def __init__(self, system_app: SystemApp):
        """Create a new DBSummaryClient."""
        self.system_app = system_app
        from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory

        embedding_factory: EmbeddingFactory = self.system_app.get_component(
            "embedding_factory", component_type=EmbeddingFactory
        )
        self.embeddings = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )

    def db_summary_embedding(self, dbname, db_type):
        """Put db profile and table profile summary into vector store."""
        db_summary_client = self.create_summary_client(dbname, db_type)

        self.init_db_profile(db_summary_client, dbname)

        logger.info("db summary embedding success")

    def get_db_summary(self, dbname, query, topk):
        """Get user query related tables info."""
        from dbgpt.serve.rag.connector import VectorStoreConnector
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        vector_store_config = VectorStoreConfig(name=dbname + "_profile")
        vector_connector = VectorStoreConnector.from_default(
            CFG.VECTOR_STORE_TYPE,
            embedding_fn=self.embeddings,
            vector_store_config=vector_store_config,
        )
        from dbgpt.rag.retriever.db_schema import DBSchemaRetriever

        retriever = DBSchemaRetriever(
            top_k=topk, index_store=vector_connector.index_client
        )
        table_docs = retriever.retrieve(query)
        ans = [d.content for d in table_docs]
        return ans

    def init_db_summary(self):
        """Initialize db summary profile."""
        db_mange = CFG.local_db_manager
        dbs = db_mange.get_db_list()
        for item in dbs:
            try:
                self.db_summary_embedding(item["db_name"], item["db_type"])
            except Exception as e:
                message = traceback.format_exc()
                logger.warn(
                    f'{item["db_name"]}, {item["db_type"]} summary error!{str(e)}, '
                    f"detail: {message}"
                )

    def init_db_profile(self, db_summary_client, dbname):
        """Initialize db summary profile.

        Args:
        db_summary_client(DBSummaryClient): DB Summary Client
        dbname(str): dbname
        """
        vector_store_name = dbname + "_profile"
        from dbgpt.serve.rag.connector import VectorStoreConnector
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        vector_store_config = VectorStoreConfig(name=vector_store_name)
        vector_connector = VectorStoreConnector.from_default(
            CFG.VECTOR_STORE_TYPE,
            self.embeddings,
            vector_store_config=vector_store_config,
        )
        if not vector_connector.vector_name_exists():
            from dbgpt.rag.assembler.db_schema import DBSchemaAssembler

            db_assembler = DBSchemaAssembler.load_from_connection(
                connector=db_summary_client.db,
                index_store=vector_connector.index_client,
            )

            if len(db_assembler.get_chunks()) > 0:
                db_assembler.persist()
        else:
            logger.info(f"Vector store name {vector_store_name} exist")
        logger.info("initialize db summary profile success...")

    def delete_db_profile(self, dbname):
        """Delete db profile."""
        vector_store_name = dbname + "_profile"
        from dbgpt.serve.rag.connector import VectorStoreConnector
        from dbgpt.storage.vector_store.base import VectorStoreConfig

        vector_store_config = VectorStoreConfig(name=vector_store_name)
        vector_connector = VectorStoreConnector.from_default(
            CFG.VECTOR_STORE_TYPE,
            self.embeddings,
            vector_store_config=vector_store_config,
        )
        vector_connector.delete_vector_name(vector_store_name)
        logger.info(f"delete db profile {dbname} success")

    @staticmethod
    def create_summary_client(dbname: str, db_type: str):
        """
        Create a summary client based on the database type.

        Args:
            dbname (str): The name of the database.
            db_type (str): The type of the database.
        """
        if "graph" in db_type:
            return GdbmsSummary(dbname, db_type)
        else:
            return RdbmsSummary(dbname, db_type)
