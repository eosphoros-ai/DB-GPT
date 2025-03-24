from dataclasses import dataclass, field
from typing import List, Optional

from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.model.parameter import (
    ModelsDeployParameters,
    ModelServiceConfig,
)
from dbgpt.storage.cache.manager import ModelCacheParameters
from dbgpt.util.configure import HookConfig
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import BaseParameters
from dbgpt.util.tracer import TracerParameters
from dbgpt.util.utils import LoggingParameters
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnectorParameters
from dbgpt_ext.storage.graph_store.tugraph_store import TuGraphStoreConfig
from dbgpt_ext.storage.vector_store.chroma_store import ChromaVectorConfig
from dbgpt_ext.storage.vector_store.elastic_store import ElasticsearchStoreConfig
from dbgpt_serve.core import BaseServeConfig
from dbgpt_serve.core.config import GPTsAppConfig


@dataclass
class SystemParameters:
    """System parameters."""

    language: str = field(
        default="en",
        metadata={
            "help": _("Language setting"),
            "valid_values": ["en", "zh", "fr", "ja", "ko", "ru"],
        },
    )
    log_level: str = field(
        default="INFO",
        metadata={
            "help": _("Logging level"),
            "valid_values": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
    )
    api_keys: List[str] = field(
        default_factory=list,
        metadata={
            "help": _("API keys"),
        },
    )
    encrypt_key: Optional[str] = field(
        default="your_secret_key",
        metadata={"help": _("The key to encrypt the data")},
    )


@dataclass
class StorageConfig(BaseParameters):
    __cfg_type__ = "app"

    vector: Optional[ChromaVectorConfig] = field(
        default_factory=lambda: ChromaVectorConfig(),
        metadata={
            "help": _("default vector type"),
        },
    )
    graph: Optional[TuGraphStoreConfig] = field(
        default=None,
        metadata={
            "help": _("default graph type"),
        },
    )
    full_text: Optional[ElasticsearchStoreConfig] = field(
        default=None,
        metadata={
            "help": _("default full text type"),
        },
    )


@dataclass
class RagParameters(BaseParameters):
    """Rag configuration."""

    __cfg_type__ = "app"

    chunk_size: Optional[int] = field(
        default=500,
        metadata={"help": _("Whether to verify the SSL certificate of the database")},
    )
    chunk_overlap: Optional[int] = field(
        default=50,
        metadata={
            "help": _(
                "The default thread pool size, If None, use default config of python "
                "thread pool"
            )
        },
    )
    similarity_top_k: Optional[int] = field(
        default=10,
        metadata={"help": _("knowledge search top k")},
    )
    similarity_score_threshold: Optional[float] = field(
        default=0.0,
        metadata={"help": _("knowledge search top similarity score")},
    )
    query_rewrite: Optional[bool] = field(
        default=False,
        metadata={"help": _("knowledge search rewrite")},
    )
    max_chunks_once_load: Optional[int] = field(
        default=10,
        metadata={"help": _("knowledge max chunks once load")},
    )
    max_threads: Optional[int] = field(
        default=1,
        metadata={"help": _("knowledge max load thread")},
    )
    rerank_top_k: Optional[int] = field(
        default=3,
        metadata={"help": _("knowledge rerank top k")},
    )
    storage: StorageConfig = field(
        default_factory=lambda: StorageConfig(),
        metadata={"help": _("Storage configuration")},
    )
    knowledge_graph_chunk_search_top_k: Optional[int] = field(
        default=5,
        metadata={"help": _("knowledge graph search top k")},
    )
    kg_enable_summary: Optional[bool] = field(
        default=False,
        metadata={"help": _("graph community summary enabled")},
    )
    llm_model: Optional[str] = field(
        default=None,
        metadata={"help": _("kg extract llm model")},
    )
    kg_extract_top_k: Optional[int] = field(
        default=5,
        metadata={"help": _("kg extract top k")},
    )
    kg_extract_score_threshold: Optional[float] = field(
        default=0.3,
        metadata={"help": _("kg extract score threshold")},
    )
    kg_community_top_k: Optional[int] = field(
        default=50,
        metadata={"help": _("kg community top k")},
    )
    kg_community_score_threshold: Optional[float] = field(
        default=0.3,
        metadata={"help": _("kg_community_score_threshold")},
    )
    kg_triplet_graph_enabled: Optional[bool] = field(
        default=True,
        metadata={"help": _("kg_triplet_graph_enabled")},
    )
    kg_document_graph_enabled: Optional[bool] = field(
        default=True,
        metadata={"help": _("kg_document_graph_enabled")},
    )
    kg_chunk_search_top_k: Optional[int] = field(
        default=5,
        metadata={"help": _("kg_chunk_search_top_k")},
    )
    kg_extraction_batch_size: Optional[int] = field(
        default=3,
        metadata={"help": _("kg_extraction_batch_size")},
    )
    kg_community_summary_batch_size: Optional[int] = field(
        default=20,
        metadata={"help": _("kg_community_summary_batch_size")},
    )
    kg_embedding_batch_size: Optional[int] = field(
        default=20,
        metadata={"help": _("kg_embedding_batch_size")},
    )
    kg_similarity_top_k: Optional[int] = field(
        default=5,
        metadata={"help": _("kg_similarity_top_k")},
    )
    kg_similarity_score_threshold: Optional[float] = field(
        default=0.7,
        metadata={"help": _("kg_similarity_score_threshold")},
    )
    kg_enable_text_search: Optional[bool] = field(
        default=False,
        metadata={"help": _("kg_enable_text_search")},
    )
    kg_text2gql_model_enabled: Optional[bool] = field(
        default=False,
        metadata={"help": _("kg_text2gql_model_enabled")},
    )
    kg_text2gql_model_name: Optional[str] = field(
        default=None,
        metadata={"help": _("text2gql_model_name")},
    )
    bm25_k1: Optional[float] = field(
        default=2.0,
        metadata={"help": _("bm25_k1")},
    )
    bm25_b: Optional[float] = field(
        default=0.75,
        metadata={"help": _("bm25_b")},
    )


@dataclass
class ServiceWebParameters(BaseParameters):
    __cfg_type__ = "service"
    host: str = field(default="0.0.0.0", metadata={"help": _("Webserver deploy host")})
    port: int = field(
        default=5670, metadata={"help": _("Webserver deploy port, default is 5670")}
    )
    light: Optional[bool] = field(
        default=False, metadata={"help": _("Run Webserver in light mode")}
    )
    controller_addr: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The Model controller address to connect. If None, read model "
                "controller address from environment key `MODEL_SERVER`."
            )
        },
    )
    database: BaseDatasourceParameters = field(
        default_factory=lambda: SQLiteConnectorParameters(
            path="pilot/meta_data/dbgpt.db"
        ),
        metadata={
            "help": _(
                "Database connection config, now support SQLite, OceanBase and MySQL"
            )
        },
    )
    model_storage: Optional[str] = field(
        default=None,
        metadata={
            "help": _(
                "The storage type of model configures, if None, use the default "
                "storage(current database). When you run in light mode, it will not "
                "use any storage."
            ),
            "valid_values": ["database", "memory"],
        },
    )
    trace: Optional[TracerParameters] = field(
        default=None,
        metadata={
            "help": _("Tracer config for web server, if None, use global tracer config")
        },
    )
    log: Optional[LoggingParameters] = field(
        default=None,
        metadata={
            "help": _(
                "Logging configuration for web server, if None, use global config"
            )
        },
    )
    disable_alembic_upgrade: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to disable alembic to initialize and upgrade database metadata"
            )
        },
    )
    db_ssl_verify: Optional[bool] = field(
        default=False,
        metadata={"help": _("Whether to verify the SSL certificate of the database")},
    )
    default_thread_pool_size: Optional[int] = field(
        default=None,
        metadata={
            "help": _(
                "The default thread pool size, If None, use default config of python "
                "thread pool"
            )
        },
    )
    remote_embedding: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to enable remote embedding models. If it is True, you need"
                " to start a embedding model through `dbgpt start worker --worker_type "
                "text2vec --model_name xxx --model_path xxx`"
            )
        },
    )
    remote_rerank: Optional[bool] = field(
        default=False,
        metadata={
            "help": _(
                "Whether to enable remote rerank models. If it is True, you need"
                " to start a rerank model through `dbgpt start worker --worker_type "
                "text2vec --rerank --model_name xxx --model_path xxx`"
            )
        },
    )
    awel_dirs: Optional[str] = field(
        default=None,
        metadata={"help": _("The directories to search awel files, split by `,`")},
    )
    new_web_ui: bool = field(
        default=True,
        metadata={"help": _("Whether to use the new web UI, default is True")},
    )
    model_cache: ModelCacheParameters = field(
        default_factory=ModelCacheParameters,
        metadata={"help": _("Model cache configuration")},
    )
    embedding_model_max_seq_len: Optional[int] = field(
        default=512,
        metadata={
            "help": _("The max sequence length of the embedding model, default is 512")
        },
    )


@dataclass
class ServiceConfig(BaseParameters):
    __cfg_type__ = "service"

    web: ServiceWebParameters = field(
        default_factory=ServiceWebParameters,
        metadata={"help": _("Web service configuration")},
    )
    model: ModelServiceConfig = field(
        default_factory=ModelServiceConfig,
        metadata={"help": _("Model service configuration")},
    )


@dataclass
class ApplicationConfig(BaseParameters):
    """Application configuration."""

    hooks: List[HookConfig] = field(
        default_factory=list,
        metadata={
            "help": _(
                "Configuration hooks, which will be executed before the configuration "
                "loading"
            ),
        },
    )

    system: SystemParameters = field(
        default_factory=SystemParameters,
        metadata={
            "help": _("System configuration"),
        },
    )
    service: ServiceConfig = field(default_factory=ServiceConfig)
    models: ModelsDeployParameters = field(
        default_factory=ModelsDeployParameters,
        metadata={
            "help": _("Model deployment configuration"),
        },
    )
    serves: List[BaseServeConfig] = field(
        default_factory=list,
        metadata={
            "help": _("Serve configuration"),
        },
    )
    rag: RagParameters = field(
        default_factory=lambda: RagParameters(),
        metadata={"help": _("Rag Knowledge Parameters")},
    )
    app: GPTsAppConfig = field(
        default_factory=lambda: GPTsAppConfig(),
        metadata={"help": _("GPTs application configuration")},
    )
    trace: TracerParameters = field(
        default_factory=TracerParameters,
        metadata={
            "help": _("Global tracer configuration"),
        },
    )
    log: LoggingParameters = field(
        default_factory=LoggingParameters,
        metadata={
            "help": _("Logging configuration"),
        },
    )
