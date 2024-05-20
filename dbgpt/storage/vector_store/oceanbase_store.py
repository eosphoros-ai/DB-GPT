"""OceanBase vector store."""
import json
import logging
import os
import threading
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import Field
from sqlalchemy import Column, Table, create_engine, insert, text
from sqlalchemy.dialects.mysql import JSON, LONGTEXT, VARCHAR
from sqlalchemy.types import String, UserDefinedType

from dbgpt.core import Chunk, Document, Embeddings
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.vector_store.base import (
    _COMMON_PARAMETERS,
    VectorStoreBase,
    VectorStoreConfig,
)
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.i18n_utils import _

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base


logger = logging.getLogger(__name__)
sql_logger = None
sql_dbg_log_path = os.getenv("OB_SQL_DBG_LOG_PATH", "")
if sql_dbg_log_path != "":
    sql_logger = logging.getLogger("ob_sql_dbg")
    sql_logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(sql_dbg_log_path)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    sql_logger.addHandler(file_handler)

_OCEANBASE_DEFAULT_EMBEDDING_DIM = 1536
_OCEANBASE_DEFAULT_COLLECTION_NAME = "langchain_document"
_OCEANBASE_DEFAULT_IVFFLAT_ROW_THRESHOLD = 10000
_OCEANBASE_DEFAULT_RWLOCK_MAX_READER = 64

Base = declarative_base()


def ob_vector_from_db(value):
    """Parse vector from oceanbase."""
    return [float(v) for v in value[1:-1].split(",")]


def ob_vector_to_db(value, dim=None):
    """Parse vector to oceanbase vector constant type."""
    if value is None:
        return value

    return "[" + ",".join([str(float(v)) for v in value]) + "]"


class Vector(UserDefinedType):
    """OceanBase Vector Column Type."""

    cache_ok = True
    _string = String()

    def __init__(self, dim):
        """Create a Vector column with dimemsion `dim`."""
        super(UserDefinedType, self).__init__()
        self.dim = dim

    def get_col_spec(self, **kw):
        """Get vector column definition in string format."""
        return "VECTOR(%d)" % self.dim

    def bind_processor(self, dialect):
        """Get a processor to parse an array to oceanbase vector."""

        def process(value):
            return ob_vector_to_db(value, self.dim)

        return process

    def literal_processor(self, dialect):
        """Get a string processor to parse an array to OceanBase Vector."""
        string_literal_processor = self._string._cached_literal_processor(dialect)

        def process(value):
            return string_literal_processor(ob_vector_to_db(value, self.dim))

        return process

    def result_processor(self, dialect, coltype):
        """Get a processor to parse OceanBase Vector to array."""

        def process(value):
            return ob_vector_from_db(value)

        return process


class OceanBaseCollectionStat:
    """A tracer that maintains a table status in OceanBase."""

    def __init__(self):
        """Create OceanBaseCollectionStat instance."""
        self._lock = threading.Lock()
        self.maybe_collection_not_exist = True
        self.maybe_collection_index_not_exist = True

    def collection_exists(self):
        """Set a table is existing."""
        with self._lock:
            self.maybe_collection_not_exist = False

    def collection_index_exists(self):
        """Set the index of a table is existing."""
        with self._lock:
            self.maybe_collection_index_not_exist = False

    def collection_not_exists(self):
        """Set a table is dropped."""
        with self._lock:
            self.maybe_collection_not_exist = True

    def collection_index_not_exists(self):
        """Set the index of a table is dropped."""
        with self._lock:
            self.maybe_collection_index_not_exist = True

    def get_maybe_collection_not_exist(self):
        """Get the existing status of a table."""
        with self._lock:
            return self.maybe_collection_not_exist

    def get_maybe_collection_index_not_exist(self):
        """Get the existing stats of the index of a table."""
        with self._lock:
            return self.maybe_collection_index_not_exist


class OceanBaseGlobalRWLock:
    """A global rwlock for OceanBase to do creating vector index table offline ddl."""

    def __init__(self, max_readers) -> None:
        """Create a rwlock."""
        self.max_readers_ = max_readers
        self.writer_entered_ = False
        self.reader_cnt_ = 0
        self.mutex_ = threading.Lock()
        self.writer_cv_ = threading.Condition(self.mutex_)
        self.reader_cv_ = threading.Condition(self.mutex_)

    def rlock(self):
        """Lock for reading."""
        self.mutex_.acquire()
        while self.writer_entered_ or self.max_readers_ == self.reader_cnt_:
            self.reader_cv_.wait()
        self.reader_cnt_ += 1
        self.mutex_.release()

    def runlock(self):
        """Unlock reading lock."""
        self.mutex_.acquire()
        self.reader_cnt_ -= 1
        if self.writer_entered_:
            if self.reader_cnt_ == 0:
                self.writer_cv_.notify(1)
        else:
            if self.max_readers_ - 1 == self.reader_cnt_:
                self.reader_cv_.notify(1)
        self.mutex_.release()

    def wlock(self):
        """Lock for writing."""
        self.mutex_.acquire()
        while self.writer_entered_:
            self.reader_cv_.wait()
        self.writer_entered_ = True
        while 0 < self.reader_cnt_:
            self.writer_cv_.wait()
        self.mutex_.release()

    def wunlock(self):
        """Unlock writing lock."""
        self.mutex_.acquire()
        self.writer_entered_ = False
        self.reader_cv_.notifyAll()
        self.mutex_.release()

    class OBRLock:
        """Reading Lock Wrapper for `with` clause."""

        def __init__(self, rwlock) -> None:
            """Create reading lock wrapper instance."""
            self.rwlock_ = rwlock

        def __enter__(self):
            """Lock."""
            self.rwlock_.rlock()

        def __exit__(self, exc_type, exc_value, traceback):
            """Unlock when exiting."""
            self.rwlock_.runlock()

    class OBWLock:
        """Writing Lock Wrapper for `with` clause."""

        def __init__(self, rwlock) -> None:
            """Create writing lock wrapper instance."""
            self.rwlock_ = rwlock

        def __enter__(self):
            """Lock."""
            self.rwlock_.wlock()

        def __exit__(self, exc_type, exc_value, traceback):
            """Unlock when exiting."""
            self.rwlock_.wunlock()

    def reader_lock(self):
        """Get reading lock wrapper."""
        return self.OBRLock(self)

    def writer_lock(self):
        """Get writing lock wrapper."""
        return self.OBWLock(self)


ob_grwlock = OceanBaseGlobalRWLock(_OCEANBASE_DEFAULT_RWLOCK_MAX_READER)


class OceanBase:
    """OceanBase Vector Store implementation."""

    def __init__(
        self,
        database: str,
        connection_string: str,
        embedding_function: Embeddings,
        embedding_dimension: int = _OCEANBASE_DEFAULT_EMBEDDING_DIM,
        collection_name: str = _OCEANBASE_DEFAULT_COLLECTION_NAME,
        pre_delete_collection: bool = False,
        logger: Optional[logging.Logger] = None,
        engine_args: Optional[dict] = None,
        delay_table_creation: bool = True,
        enable_index: bool = False,
        th_create_ivfflat_index: int = _OCEANBASE_DEFAULT_IVFFLAT_ROW_THRESHOLD,
        sql_logger: Optional[logging.Logger] = None,
        collection_stat: Optional[OceanBaseCollectionStat] = None,
        enable_normalize_vector: bool = False,
    ) -> None:
        """Create OceanBase Vector Store instance."""
        self.database = database
        self.connection_string = connection_string
        self.embedding_function = embedding_function
        self.embedding_dimension = embedding_dimension
        self.collection_name = collection_name
        self.pre_delete_collection = pre_delete_collection
        self.logger = logger or logging.getLogger(__name__)
        self.delay_table_creation = delay_table_creation
        self.th_create_ivfflat_index = th_create_ivfflat_index
        self.enable_index = enable_index
        self.sql_logger = sql_logger
        self.collection_stat = collection_stat
        self.enable_normalize_vector = enable_normalize_vector
        self.__post_init__(engine_args)

    def __post_init__(
        self,
        engine_args: Optional[dict] = None,
    ) -> None:
        """Create connection & vector table."""
        _engine_args = engine_args or {}
        if "pool_recycle" not in _engine_args:
            _engine_args["pool_recycle"] = 3600
        self.engine = create_engine(self.connection_string, **_engine_args)
        self.create_collection()

    @property
    def embeddings(self) -> Embeddings:
        """Get embedding function."""
        return self.embedding_function

    def create_collection(self) -> None:
        """Create vector table."""
        if self.pre_delete_collection:
            self.delete_collection()
        if not self.delay_table_creation and (
            self.collection_stat is None
            or self.collection_stat.get_maybe_collection_not_exist()
        ):
            self.create_table_if_not_exists()
            if self.collection_stat is not None:
                self.collection_stat.collection_exists()

    def delete_collection(self) -> None:
        """Drop vector table."""
        drop_statement = text(f"DROP TABLE IF EXISTS {self.collection_name}")
        if self.sql_logger is not None:
            self.sql_logger.debug(f"Trying to delete collection: {drop_statement}")
        with self.engine.connect() as conn, conn.begin():
            conn.execute(drop_statement)
            if self.collection_stat is not None:
                self.collection_stat.collection_not_exists()
                self.collection_stat.collection_index_not_exists()

    def create_table_if_not_exists(self) -> None:
        """Create vector table with SQL."""
        create_table_query = f"""
            CREATE TABLE IF NOT EXISTS `{self.collection_name}` (
                id VARCHAR(40) NOT NULL,
                embedding VECTOR({self.embedding_dimension}),
                document LONGTEXT,
                metadata JSON,
                PRIMARY KEY (id)
            )
        """
        if self.sql_logger is not None:
            self.sql_logger.debug(f"Trying to create table: {create_table_query}")
        with self.engine.connect() as conn, conn.begin():
            # Create the table
            conn.execute(text(create_table_query))

    def create_collection_ivfflat_index_if_not_exists(self) -> None:
        """Create ivfflat index table with SQL."""
        create_index_query = f"""
            CREATE INDEX IF NOT EXISTS `embedding_idx` on `{self.collection_name}` (
                embedding l2
            ) using ivfflat with (lists=20)
        """
        with ob_grwlock.writer_lock(), self.engine.connect() as conn, conn.begin():
            # Create Ivfflat Index
            if self.sql_logger is not None:
                self.sql_logger.debug(
                    f"Trying to create ivfflat index: {create_index_query}"
                )
            conn.execute(text(create_index_query))

    def check_table_exists(self) -> bool:
        """Whether table `collection_name` exists."""
        check_table_query = f"""
            SELECT COUNT(*) as cnt
            FROM information_schema.tables
            WHERE table_schema='{self.database}' AND table_name='{self.collection_name}'
        """
        try:
            with self.engine.connect() as conn, conn.begin(), ob_grwlock.reader_lock():
                table_exists_res = conn.execute(text(check_table_query))
                for row in table_exists_res:
                    return row.cnt > 0
                # No `cnt` rows? Just return False to pass `make mypy`
                return False
        except Exception as e:
            logger.error(f"check_table_exists error: {e}")
            return False

    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        batch_size: int = 500,
        **kwargs: Any,
    ) -> List[str]:
        """Insert texts into vector table."""
        if ids is None:
            ids = [str(uuid.uuid1()) for _ in texts]

        embeddings = self.embedding_function.embed_documents(list(texts))

        if len(embeddings) == 0:
            return ids

        if not metadatas:
            metadatas = [{} for _ in texts]

        if self.delay_table_creation and (
            self.collection_stat is None
            or self.collection_stat.get_maybe_collection_not_exist()
        ):
            self.embedding_dimension = len(embeddings[0])
            self.create_table_if_not_exists()
            self.delay_table_creation = False
            if self.collection_stat is not None:
                self.collection_stat.collection_exists()

        chunks_table = Table(
            self.collection_name,
            Base.metadata,
            Column("id", VARCHAR(40), primary_key=True),
            Column("embedding", Vector(self.embedding_dimension)),
            Column("document", LONGTEXT, nullable=True),
            Column("metadata", JSON, nullable=True),  # filter
            keep_existing=True,
        )

        row_count_query = f"""
            SELECT COUNT(*) as cnt FROM `{self.collection_name}`
        """
        chunks_table_data = []
        with self.engine.connect() as conn, conn.begin():
            for document, metadata, chunk_id, embedding in zip(
                texts, metadatas, ids, embeddings
            ):
                chunks_table_data.append(
                    {
                        "id": chunk_id,
                        "embedding": embedding
                        if not self.enable_normalize_vector
                        else self._normalization_vectors(embedding),
                        "document": document,
                        "metadata": metadata,
                    }
                )

                # Execute the batch insert when the batch size is reached
                if len(chunks_table_data) == batch_size:
                    with ob_grwlock.reader_lock():
                        if self.sql_logger is not None:
                            insert_sql_for_log = str(
                                insert(chunks_table).values(chunks_table_data)
                            )
                            self.sql_logger.debug(
                                f"""Trying to insert vectors:
                                    {insert_sql_for_log}"""
                            )
                        conn.execute(insert(chunks_table).values(chunks_table_data))
                    # Clear the chunks_table_data list for the next batch
                    chunks_table_data.clear()

            # Insert any remaining records that didn't make up a full batch
            if chunks_table_data:
                with ob_grwlock.reader_lock():
                    if self.sql_logger is not None:
                        insert_sql_for_log = str(
                            insert(chunks_table).values(chunks_table_data)
                        )
                        self.sql_logger.debug(
                            f"""Trying to insert vectors:
                                {insert_sql_for_log}"""
                        )
                    conn.execute(insert(chunks_table).values(chunks_table_data))

            if self.enable_index and (
                self.collection_stat is None
                or self.collection_stat.get_maybe_collection_index_not_exist()
            ):
                with ob_grwlock.reader_lock():
                    row_cnt_res = conn.execute(text(row_count_query))
                for row in row_cnt_res:
                    if row.cnt > self.th_create_ivfflat_index:
                        self.create_collection_ivfflat_index_if_not_exists()
                        if self.collection_stat is not None:
                            self.collection_stat.collection_index_exists()

        return ids

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[MetadataFilters] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Do similarity search via query in String."""
        embedding = self.embedding_function.embed_query(query)
        docs = self.similarity_search_by_vector(embedding=embedding, k=k, filter=filter)
        return docs

    def similarity_search_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[MetadataFilters] = None,
        **kwargs: Any,
    ) -> List[Document]:
        """Do similarity search via query vector."""
        docs_and_scores = self.similarity_search_with_score_by_vector(
            embedding=embedding, k=k, filter=filter
        )
        return [doc for doc, _ in docs_and_scores]

    def similarity_search_with_score_by_vector(
        self,
        embedding: List[float],
        k: int = 4,
        filter: Optional[MetadataFilters] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[Document, float]]:
        """Do similarity search via query vector with score."""
        try:
            from sqlalchemy.engine import Row
        except ImportError:
            raise ImportError(
                "Could not import Row from sqlalchemy.engine. "
                "Please 'pip install sqlalchemy>=1.4'."
            )

        # filter is not support in OceanBase currently.

        # normailze embedding vector
        if self.enable_normalize_vector:
            embedding = self._normalization_vectors(embedding)

        embedding_str = ob_vector_to_db(embedding, self.embedding_dimension)
        vector_distance_op = "<@>" if self.enable_normalize_vector else "<->"
        sql_query = f"""
            SELECT document, metadata, embedding {vector_distance_op} '{embedding_str}'
            as distance
            FROM {self.collection_name}
            ORDER BY embedding {vector_distance_op} '{embedding_str}'
            LIMIT :k
        """
        sql_query_str_for_log = f"""
            SELECT document, metadata, embedding {vector_distance_op} '?' as distance
            FROM {self.collection_name}
            ORDER BY embedding {vector_distance_op} '?'
            LIMIT {k}
        """

        params = {"k": k}
        try:
            with ob_grwlock.reader_lock(), self.engine.connect() as conn:
                if self.sql_logger is not None:
                    self.sql_logger.debug(
                        f"Trying to do similarity search: {sql_query_str_for_log}"
                    )
                results: Sequence[Row] = conn.execute(
                    text(sql_query), params
                ).fetchall()

            if (score_threshold is not None) and self.enable_normalize_vector:
                documents_with_scores = [
                    (
                        Document(
                            content=result.document,
                            metadata=json.loads(result.metadata),
                        ),
                        result.distance,
                    )
                    for result in results
                    if result.distance >= score_threshold
                ]
            else:
                documents_with_scores = [
                    (
                        Document(
                            content=result.document,
                            metadata=json.loads(result.metadata),
                        ),
                        result.distance,
                    )
                    for result in results
                ]
            return documents_with_scores
        except Exception as e:
            self.logger.error("similarity_search_with_score_by_vector failed:", str(e))
            return []

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 4,
        filter: Optional[MetadataFilters] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[Document, float]]:
        """Do similarity search via query String with score."""
        embedding = self.embedding_function.embed_query(query)
        docs = self.similarity_search_with_score_by_vector(
            embedding=embedding, k=k, filter=filter, score_threshold=score_threshold
        )
        return docs

    def delete(self, ids: Optional[List[str]] = None, **kwargs: Any) -> Optional[bool]:
        """Delete vectors from vector table."""
        if ids is None:
            raise ValueError("No ids provided to delete.")

        # Define the table schema
        chunks_table = Table(
            self.collection_name,
            Base.metadata,
            Column("id", VARCHAR(40), primary_key=True),
            Column("embedding", Vector(self.embedding_dimension)),
            Column("document", LONGTEXT, nullable=True),
            Column("metadata", JSON, nullable=True),  # filter
            keep_existing=True,
        )

        try:
            with self.engine.connect() as conn, conn.begin():
                delete_condition = chunks_table.c.id.in_(ids)
                delete_stmt = chunks_table.delete().where(delete_condition)
                with ob_grwlock.reader_lock():
                    if self.sql_logger is not None:
                        self.sql_logger.debug(
                            f"Trying to delete vectors: {str(delete_stmt)}"
                        )
                    conn.execute(delete_stmt)
                return True
        except Exception as e:
            self.logger.error("Delete operation failed:", str(e))
            return False

    def _normalization_vectors(self, vector):
        import numpy as np

        norm = np.linalg.norm(vector)
        return (vector / norm).tolist()

    @classmethod
    def connection_string_from_db_params(
        cls,
        host: str,
        port: int,
        database: str,
        user: str,
        password: str,
    ) -> str:
        """Get connection string."""
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"


ob_collection_stats_lock = threading.Lock()
ob_collection_stats: Dict[str, OceanBaseCollectionStat] = {}


@register_resource(
    _("OceanBase Vector Store"),
    "oceanbase_vector_store",
    category=ResourceCategory.VECTOR_STORE,
    parameters=[
        *_COMMON_PARAMETERS,
        Parameter.build_from(
            _("OceanBase Host"),
            "ob_host",
            str,
            description=_("oceanbase host"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase Port"),
            "ob_port",
            int,
            description=_("oceanbase port"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase User"),
            "ob_user",
            str,
            description=_("user to login"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase Password"),
            "ob_password",
            str,
            description=_("password to login"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("OceanBase Database"),
            "ob_database",
            str,
            description=_("database for vector tables"),
            optional=True,
            default=None,
        ),
    ],
    description="OceanBase vector store.",
)
class OceanBaseConfig(VectorStoreConfig):
    """OceanBase vector store config."""

    class Config:
        """Config for BaseModel."""

        arbitrary_types_allowed = True

    """OceanBase config"""
    ob_host: str = Field(
        default="127.0.0.1",
        description="oceanbase host",
    )
    ob_port: int = Field(
        default=2881,
        description="oceanbase port",
    )
    ob_user: str = Field(
        default="root@test",
        description="user to login",
    )
    ob_password: str = Field(
        default="",
        description="password to login",
    )
    ob_database: str = Field(
        default="test",
        description="database for vector tables",
    )


class OceanBaseStore(VectorStoreBase):
    """OceanBase vector store."""

    def __init__(self, vector_store_config: OceanBaseConfig) -> None:
        """Create a OceanBaseStore instance."""
        if vector_store_config.embedding_fn is None:
            raise ValueError("embedding_fn is required for OceanBaseStore")
        super().__init__()
        self.embeddings = vector_store_config.embedding_fn
        self.collection_name = vector_store_config.name
        vector_store_config = vector_store_config.dict()
        self.OB_HOST = str(
            vector_store_config.get("ob_host") or os.getenv("OB_HOST", "127.0.0.1")
        )
        self.OB_PORT = int(
            vector_store_config.get("ob_port") or int(os.getenv("OB_PORT", "2881"))
        )
        self.OB_USER = str(
            vector_store_config.get("ob_user") or os.getenv("OB_USER", "root@test")
        )
        self.OB_PASSWORD = str(
            vector_store_config.get("ob_password") or os.getenv("OB_PASSWORD", "")
        )
        self.OB_DATABASE = str(
            vector_store_config.get("ob_database") or os.getenv("OB_DATABASE", "test")
        )
        self.OB_ENABLE_NORMALIZE_VECTOR = bool(
            os.getenv("OB_ENABLE_NORMALIZE_VECTOR", "")
        )
        self.connection_string = OceanBase.connection_string_from_db_params(
            self.OB_HOST, self.OB_PORT, self.OB_DATABASE, self.OB_USER, self.OB_PASSWORD
        )
        self.logger = logger
        with ob_collection_stats_lock:
            if ob_collection_stats.get(self.collection_name) is None:
                ob_collection_stats[self.collection_name] = OceanBaseCollectionStat()
            self.collection_stat = ob_collection_stats[self.collection_name]

        self.vector_store_client = OceanBase(
            database=self.OB_DATABASE,
            connection_string=self.connection_string,
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
            logger=self.logger,
            sql_logger=sql_logger,
            enable_index=bool(os.getenv("OB_ENABLE_INDEX", "")),
            collection_stat=self.collection_stat,
            enable_normalize_vector=self.OB_ENABLE_NORMALIZE_VECTOR,
        )

    def similar_search(
        self, text, topk, filters: Optional[MetadataFilters] = None, **kwargs: Any
    ) -> List[Chunk]:
        """Perform a search on a query string and return results."""
        self.logger.info("OceanBase: similar_search..")
        documents = self.vector_store_client.similarity_search(
            text, topk, filter=filters
        )
        return [Chunk(content=doc.content, metadata=doc.metadata) for doc in documents]

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Perform a search on a query string and return results with score."""
        self.logger.info("OceanBase: similar_search_with_scores..")
        docs_and_scores = self.vector_store_client.similarity_search_with_score(
            text, topk, filter=filters
        )
        return [
            Chunk(content=doc.content, metadata=doc.metadata, score=score)
            for doc, score in docs_and_scores
        ]

    def vector_name_exists(self):
        """Whether vector name exists."""
        self.logger.info("OceanBase: vector_name_exists..")
        return self.vector_store_client.check_table_exists()

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Load document in vector database."""
        self.logger.info("OceanBase: load_document..")
        # lc_documents = [Chunk.chunk2langchain(chunk) for chunk in chunks]
        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        ids = self.vector_store_client.add_texts(texts=texts, metadatas=metadatas)
        return ids

    def delete_vector_name(self, vector_name):
        """Delete vector name."""
        self.logger.info("OceanBase: delete_vector_name..")
        return self.vector_store_client.delete_collection()

    def delete_by_ids(self, ids):
        """Delete vector by ids."""
        self.logger.info("OceanBase: delete_by_ids..")
        ids = ids.split(",")
        if len(ids) > 0:
            self.vector_store_client.delete(ids)
