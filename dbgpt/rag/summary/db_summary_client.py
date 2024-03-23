"""DBSummaryClient class."""

import logging
import traceback
from operator import itemgetter

from langchain_community.vectorstores.pgvector import PGVector

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.rag.retriever.bm25 import calcuate_bm25
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

        # ATL modify for PGVector==
        if CFG.VECTOR_STORE_TYPE.lower() == "pgvector":
            self.connect_string = CFG.CONNECTION_STRING

    def db_summary_embedding(self, dbname, db_type):
        """put db profile and table profile summary into vector store"""

        db_summary_client = RdbmsSummary(dbname, db_type)
        print('db_summary_client', dbname, db_type, db_summary_client)
        self.init_db_profile(db_summary_client, dbname)

        logger.info("db summary embedding success")

    def get_db_summary(self, dbname, query, topk):
        """get user query related tables info"""

        # ATL modify for PGVector==
        if CFG.VECTOR_STORE_TYPE.lower() == "pgvector":
            from dbgpt.storage.vector_store.pgvector_store import PGVectorConfig
            vector_store_config = PGVectorConfig(name=dbname + "_profile", connection_string=self.connect_string)
        else:
            from dbgpt.storage.vector_store.base import VectorStoreConfig
            vector_store_config = VectorStoreConfig(name=dbname + "_profile")

        from dbgpt.storage.vector_store.connector import VectorStoreConnector

        vector_connector = VectorStoreConnector.from_default(
            CFG.VECTOR_STORE_TYPE,
            embedding_fn=self.embeddings,
            vector_store_config=vector_store_config,
        )
        from dbgpt.rag.retriever.db_schema import DBSchemaRetriever

        retriever = DBSchemaRetriever(
            top_k=topk, vector_store_connector=vector_connector
        )
        table_docs = retriever.retrieve(query)
        try:
            ans = [d.content for d in table_docs]
        except:
            ans = [d.page_content for d in table_docs]
        return ans

    def get_db_bm25(self, dbname, query, threshold: float):
        """get user query related tables info"""

        if CFG.VECTOR_STORE_TYPE.lower() == "pgvector":
            from dbgpt.storage.vector_store.pgvector_store import PGVectorConfig, PGVectorStore
            vector_store_config = PGVectorConfig(name=dbname + "_profile", connection_string=self.connect_string)
            vector_store = PGVectorStore(vector_store_config)
        else:
            from dbgpt.storage.vector_store.base import VectorStoreConfig, VectorStoreBase
            vector_store_config = VectorStoreConfig(name=dbname + "_profile")
            vector_store = VectorStoreBase(vector_store_config)

        table_docs = vector_store.dbname_dbm25()

        result = []
        res_socre_normalize = calcuate_bm25(table_docs, query)
        docs_with_score = [(doc, score) for doc, score in zip(table_docs, res_socre_normalize)]
        docs_with_score.sort(key=itemgetter(1), reverse=True)

        for doc, score in docs_with_score:
            if float(score) >= threshold and float(score) >= 0:
                result.append(doc)
        return result

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
        from dbgpt.storage.vector_store.base import VectorStoreConfig
        from dbgpt.storage.vector_store.connector import VectorStoreConnector

        if CFG.VECTOR_STORE_TYPE == 'PGVector':
            from dbgpt.storage.vector_store.pgvector_store import PGVectorConfig
            vector_store_config = PGVectorConfig(connection_string=CFG.CONNECTION_STRING, name=vector_store_name)
        else:
            vector_store_config = VectorStoreConfig(name=vector_store_name)

        vector_connector = VectorStoreConnector.from_default(
            CFG.VECTOR_STORE_TYPE,
            self.embeddings,
            vector_store_config=vector_store_config,
        )
        if not vector_connector.vector_name_exists():

            from dbgpt.serve.rag.assembler.db_schema import DBSchemaAssembler

            db_assembler = DBSchemaAssembler.load_from_connection(
                connection=db_summary_client.db, vector_store_connector=vector_connector
            )
            if len(db_assembler.get_chunks()) > 0:
                db_assembler.persist()
        else:
            logger.info(f"Vector store name {vector_store_name} exist")
        logger.info("initialize db summary profile success...")

    def delete_db_profile(self, del_collection_name):
        db = PGVector(
            connection_string=self.connect_string,
            embedding_function=self.embeddings,
            collection_name=del_collection_name
        )
        db.delete_collection()


if __name__ == '__main__':
    system_app = SystemApp()
    dbc = DBSummaryClient(system_app)

    print(dbc.get_db_summary('type3_qasamples_profile',
                             '公司有多少人？',
                             '50', ))
