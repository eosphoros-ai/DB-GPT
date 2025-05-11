"""DBSummaryClient class."""

import logging
import traceback
from typing import Tuple

from dbgpt.component import SystemApp
from dbgpt.core import Embeddings
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.text_splitter.text_splitter import RDBTextSplitter
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt_ext.rag import ChunkParameters
from dbgpt_ext.rag.summary.gdbms_db_summary import GdbmsSummary
from dbgpt_ext.rag.summary.rdbms_db_summary import RdbmsSummary
from dbgpt_serve.datasource.manages import ConnectorManager
from dbgpt_serve.rag.storage_manager import StorageManager

logger = logging.getLogger(__name__)


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

        self.app_config = self.system_app.config.configs.get("app_config")
        self.storage_config = self.app_config.rag.storage

    @property
    def embeddings(self) -> Embeddings:
        """Get the embeddings."""
        embedding_factory: EmbeddingFactory = self.system_app.get_component(
            "embedding_factory", component_type=EmbeddingFactory
        )
        return embedding_factory.create()

    def db_summary_embedding(self, dbname, db_type):
        """Put db profile and table profile summary into vector store."""
        try:
            db_summary_client = self.create_summary_client(dbname, db_type)

            self.init_db_profile(db_summary_client, dbname)

            logger.info("db summary embedding success")
        except Exception as e:
            message = traceback.format_exc()
            logger.warning(
                f"{dbname}, {db_type} summary error!{str(e)}, detail: {message}"
            )
            raise

    def get_db_summary(self, dbname, query, topk):
        """Get user query related tables info."""
        from dbgpt_ext.rag.retriever.db_schema import DBSchemaRetriever

        table_vector_connector, field_vector_connector = (
            self._get_vector_connector_by_db(dbname)
        )
        retriever = DBSchemaRetriever(
            top_k=topk,
            table_vector_store_connector=table_vector_connector,
            field_vector_store_connector=field_vector_connector,
            separator="--table-field-separator--",
        )

        table_docs = retriever.retrieve(query)
        ans = [d.content for d in table_docs]
        return ans

    def init_db_summary(self):
        """Initialize db summary profile."""
        local_db_manager = ConnectorManager.get_instance(self.system_app)
        db_mange = local_db_manager
        dbs = db_mange.get_db_list()
        for item in dbs:
            try:
                self.db_summary_embedding(item["db_name"], item["db_type"])
            except Exception as e:
                message = traceback.format_exc()
                logger.warning(
                    f"{item['db_name']}, {item['db_type']} summary error!{str(e)}, "
                    f"detail: {message}"
                )

    def init_db_profile(self, db_summary_client, dbname):
        """Initialize db summary profile.

        Args:
        db_summary_client(DBSummaryClient): DB Summary Client
        dbname(str): dbname
        """
        vector_store_name = dbname + "_profile"

        table_vector_connector, field_vector_connector = (
            self._get_vector_connector_by_db(dbname)
        )
        if not table_vector_connector.vector_name_exists():
            from dbgpt_ext.rag.assembler.db_schema import DBSchemaAssembler
            from dbgpt_ext.rag.summary.rdbms_db_summary import _DEFAULT_COLUMN_SEPARATOR

            chunk_parameters = ChunkParameters(
                text_splitter=RDBTextSplitter(
                    column_separator=_DEFAULT_COLUMN_SEPARATOR,
                    separator="--table-field-separator--",
                )
            )
            db_assembler = DBSchemaAssembler.load_from_connection(
                connector=db_summary_client.db,
                table_vector_store_connector=table_vector_connector,
                field_vector_store_connector=field_vector_connector,
                chunk_parameters=chunk_parameters,
                max_seq_length=self.app_config.service.web.embedding_model_max_seq_len,
            )

            if len(db_assembler.get_chunks()) > 0:
                db_assembler.persist()
        else:
            logger.info(f"Vector store name {vector_store_name} exist")
        logger.info("initialize db summary profile success...")

    def delete_db_profile(self, dbname):
        """Delete db profile."""
        table_vector_store_name = dbname + "_profile"
        field_vector_store_name = dbname + "_profile_field"

        table_vector_connector, field_vector_connector = (
            self._get_vector_connector_by_db(dbname)
        )

        table_vector_connector.delete_vector_name(table_vector_store_name)
        field_vector_connector.delete_vector_name(field_vector_store_name)
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

    def _get_vector_connector_by_db(
        self, dbname
    ) -> Tuple[VectorStoreBase, VectorStoreBase]:
        vector_store_name = dbname + "_profile"
        storage_manager = StorageManager.get_instance(self.system_app)
        table_vector_store = storage_manager.create_vector_store(
            index_name=vector_store_name
        )
        field_vector_store_name = dbname + "_profile_field"
        field_vector_store = storage_manager.create_vector_store(
            index_name=field_vector_store_name
        )
        return table_vector_store, field_vector_store
