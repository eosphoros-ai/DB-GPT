import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import pytest

from ...configure.manager import (
    ConfigurationManager,
    RegisterParameters,
)


@dataclass
class SystemConfig:
    language: str
    log_level: str
    api_keys: List[str]
    encrypt_key: str


@dataclass
class DatabaseConfig:
    type: str
    path: str


@dataclass
class WebConfig:
    host: str
    port: int
    database: DatabaseConfig


@dataclass
class ModelConfig:
    host: str
    port: int


@dataclass
class ModelServiceConfig:
    controller: ModelConfig
    worker: ModelConfig
    api: ModelConfig


@dataclass
class ServiceConfig:
    web: WebConfig
    model: ModelServiceConfig


@dataclass
class AppGenerationConfig:
    temperature: float
    top_k: int
    top_p: float
    max_tokens: int
    keep_start_rounds: int
    keep_end_rounds: int


@dataclass
class AppConfigItem:
    name: str
    prompt: str
    temperature: float


@dataclass
class AppConfig:
    temperature: float
    top_k: int
    top_p: float
    max_tokens: int
    keep_start_rounds: int
    keep_end_rounds: int
    configs: List[AppConfigItem]


@dataclass
class ChunkConfig:
    type: str
    chunk_size: int
    chunk_overlap: int


@dataclass
class VectorStorageConfig:
    type: str
    persist_path: str


@dataclass
class StorageConfig:
    vector: VectorStorageConfig
    graph: Dict[str, str]


@dataclass
class RagConfig:
    embedding: str
    reranker: str
    reranker_top_k: int
    max_chunks_once_load: int
    max_threads: int
    recore_score_threshold: float
    chunk: List[ChunkConfig]
    storage: StorageConfig


@dataclass
class ModelDeployConfig:
    type: str
    name: str
    path: Optional[str] = None
    inference_type: Optional[str] = None


@dataclass
class ModelsConfig:
    default_llm: str
    default_embedding: str
    default_reranker: str
    deploy: List[ModelDeployConfig]


@dataclass
class RootConfig:
    system: SystemConfig
    service: ServiceConfig
    app: AppConfig
    rag: RagConfig
    models: ModelsConfig


def test_basic_config():
    config_dict = {
        "system": {
            "language": "en",
            "log_level": "INFO",
            "api_keys": [],
            "encrypt_key": "your_secret_key",
        }
    }

    config_manager = ConfigurationManager(config_dict)
    system_config = config_manager.parse_config(SystemConfig, "system", None)

    assert system_config.language == "en"
    assert system_config.log_level == "INFO"
    assert system_config.api_keys == []
    assert system_config.encrypt_key == "your_secret_key"


def test_nested_config():
    config_dict = {
        "service": {
            "web": {
                "host": "127.0.0.1",
                "port": 5670,
                "database": {"type": "sqlite", "path": "db.sqlite3"},
            },
            "model": {
                "controller": {"host": "127.0.0.1", "port": 8000},
                "worker": {"host": "127.0.0.1", "port": 8001},
                "api": {"host": "127.0.0.1", "port": 8100},
            },
        }
    }

    config_manager = ConfigurationManager(config_dict)
    service_config = config_manager.parse_config(ServiceConfig, "service", None)

    assert service_config.web.host == "127.0.0.1"
    assert service_config.web.port == 5670
    assert service_config.web.database.type == "sqlite"
    assert service_config.web.database.path == "db.sqlite3"
    assert service_config.model.controller.port == 8000


def test_list_config():
    config_dict = {
        "models": {
            "default_llm": "glm-4-9b-chat",
            "default_embedding": "BAAI/bge-large-zh-v1.5",
            "default_reranker": "BAAI/bge-reranker-v2-m3",
            "deploy": [
                {
                    "type": "llm",
                    "name": "glm-4-9b-chat",
                    "path": "models/glm-4-9b-chat",
                },
                {"type": "llm", "name": "qwen-max", "inference_type": "proxyllm"},
            ],
        }
    }

    config_manager = ConfigurationManager(config_dict)
    models_config = config_manager.parse_config(ModelsConfig, "models", None)

    assert models_config.default_llm == "glm-4-9b-chat"
    assert len(models_config.deploy) == 2
    assert models_config.deploy[0].type == "llm"
    assert models_config.deploy[1].inference_type == "proxyllm"


def test_optional_fields():
    config_dict = {"models": {"deploy": [{"type": "llm", "name": "model1"}]}}

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError, match="Missing required field"):
        config_manager.parse_config(ModelsConfig, "models", None)


def test_complete_config(tmp_path: Path):
    """Test complete configuration"""
    config_content = """
[system]
language = "en"
log_level = "INFO"
api_keys = []
encrypt_key = "your_secret_key"

[service.web]
host = "127.0.0.1"
port = 5670

[service.web.database]
type = "sqlite"
path = "db.sqlite3"

[service.model.controller]
host = "127.0.0.1"
port = 8000

[service.model.worker]
host = "127.0.0.1"
port = 8001

[service.model.api]
host = "127.0.0.1"
port = 8100

[app]
temperature = 0.8
top_k = 40
top_p = 0.9
max_tokens = 2048
keep_start_rounds = 2
keep_end_rounds = 3

[[app.configs]]
name = "chat_data"
prompt = "xxx"
temperature = 0.5

[rag]
embedding = "BAAI/bge-large-zh-v1.5"
reranker = "BAAI/bge-reranker-v2-m3"
reranker_top_k = 10
max_chunks_once_load = 10
max_threads = 1
recore_score_threshold = 0.3

[[rag.chunk]]
type = "CHUNK_BY_SIZE"
chunk_size = 500
chunk_overlap = 50

[rag.storage.vector]
type = "Chroma"
persist_path = "pilot/data"

[rag.storage.graph]
type = "tu_graph"

[models]
default_llm = "glm-4-9b-chat"
default_embedding = "BAAI/bge-large-zh-v1.5"
default_reranker = "BAAI/bge-reranker-v2-m3"

[[models.deploy]]
type = "llm"
name = "glm-4-9b-chat"
path = "models/glm-4-9b-chat"

[[models.deploy]]
type = "llm"
name = "qwen-max"
inference_type = "proxyllm"
    """

    config_file = tmp_path / "test_config.toml"
    config_file.write_text(config_content)

    config_manager = ConfigurationManager.from_file(config_file)
    root_config = config_manager.parse_config(RootConfig)

    # Verify system configuration
    assert root_config.system.language == "en"
    assert root_config.system.log_level == "INFO"

    # verify web service configuration
    assert root_config.service.web.host == "127.0.0.1"
    assert root_config.service.web.port == 5670
    assert root_config.service.web.database.type == "sqlite"

    # Verify model service configuration
    assert root_config.service.model.controller.port == 8000
    assert root_config.service.model.worker.port == 8001
    assert root_config.service.model.api.port == 8100

    # Verify app configuration
    assert root_config.app.temperature == 0.8
    assert root_config.app.top_k == 40
    assert len(root_config.app.configs) == 1
    assert root_config.app.configs[0].name == "chat_data"

    # Verify RAG configuration
    assert root_config.rag.embedding == "BAAI/bge-large-zh-v1.5"
    assert len(root_config.rag.chunk) == 1
    assert root_config.rag.chunk[0].chunk_size == 500
    assert root_config.rag.storage.vector.type == "Chroma"

    # Verify model deployment configuration
    assert len(root_config.models.deploy) == 2
    assert root_config.models.deploy[0].type == "llm"
    assert root_config.models.deploy[1].inference_type == "proxyllm"


def test_missing_section():
    """Test missing configuration section"""
    config_dict = {
        "system": {
            "language": "${env:LANG:-en}",
            "log_level": "${env:LOG_LEVEL:-INFO}",
            "api_keys": [],
            "encrypt_key": "${env:ENCRYPT_KEY:-https://api.openai.com/v1}",
        }
    }

    # Test with unset environment variables
    if "LANG" in os.environ:
        del os.environ["LANG"]
    if "LOG_LEVEL" in os.environ:
        del os.environ["LOG_LEVEL"]
    if "ENCRYPT_KEY" in os.environ:
        del os.environ["ENCRYPT_KEY"]

    config_manager = ConfigurationManager(config_dict)
    config_manager.parse_config(SystemConfig, "system", None)


def test_invalid_config_type():
    """Test invalid type for integer field"""
    config_dict = {
        "service": {
            "web": {
                "host": "127.0.0.1",
                "port": "invalid_port",  # Here should be an integer
                "database": {"type": "sqlite", "path": "db.sqlite3"},
            }
        }
    }

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError):
        config_manager.parse_config(ServiceConfig, "service", None)


def test_nested_optional_fields():
    """Test optional nested fields"""
    config_dict = {
        "models": {
            "default_llm": "glm-4-9b-chat",
            "default_embedding": "BAAI/bge-large-zh-v1.5",
            "default_reranker": "BAAI/bge-reranker-v2-m3",
            "deploy": [
                {
                    "type": "llm",
                    "name": "glm-4-9b-chat",
                    # Optional fields are missing
                }
            ],
        }
    }

    config_manager = ConfigurationManager(config_dict)
    models_config = config_manager.parse_config(ModelsConfig, "models", None)

    assert models_config.deploy[0].path is None
    assert models_config.deploy[0].inference_type is None


def test_empty_list_fields():
    """Test empty list field"""
    config_dict = {
        "app": {
            "temperature": 0.8,
            "top_k": 40,
            "top_p": 0.9,
            "max_tokens": 2048,
            "keep_start_rounds": 2,
            "keep_end_rounds": 3,
            "configs": [],  # Empty list
        }
    }

    config_manager = ConfigurationManager(config_dict)
    app_config = config_manager.parse_config(AppConfig, "app", None)
    assert len(app_config.configs) == 0


def test_dict_field_types():
    """Test dictionary element type mismatch"""
    config_dict = {
        "rag": {
            "embedding": "test",
            "reranker": "test",
            "reranker_top_k": 10,
            "max_chunks_once_load": 10,
            "max_threads": 1,
            "recore_score_threshold": 0.3,
            "chunk": [],
            "storage": {
                "vector": {"type": "Chroma", "persist_path": "test"},
                "graph": {
                    "type": "tu_graph",
                    "extra_param": "value",
                },  # Extra parameter
            },
        }
    }

    config_manager = ConfigurationManager(config_dict)
    rag_config = config_manager.parse_config(RagConfig, "rag", None)
    assert isinstance(rag_config.storage.graph, dict)
    assert rag_config.storage.graph["extra_param"] == "value"


def test_deep_nested_config():
    """Test deep nested configuration"""
    config_dict = {
        "service": {
            "model": {
                "controller": {"host": "localhost", "port": 8000},
                "worker": {"host": "localhost", "port": 8001},
                "api": {"host": "localhost", "port": 8002},
            },
            "web": {
                "host": "localhost",
                "port": 8003,
                "database": {"type": "sqlite", "path": "test.db"},
            },
        }
    }

    config_manager = ConfigurationManager(config_dict)
    service_config = config_manager.parse_config(ServiceConfig, "service", None)

    assert service_config.model.controller.port == 8000
    assert service_config.model.worker.port == 8001
    assert service_config.model.api.port == 8002
    assert service_config.web.port == 8003


def test_invalid_nested_type():
    """Test dictionary element type mismatch"""
    config_dict = {
        "service": {
            "web": {
                "host": "localhost",
                "port": 8080,
                "database": "invalid_database_config",  # Here should be a dictionary
            }
        }
    }

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError):
        config_manager.parse_config(ServiceConfig, "service", None)

    """Test list element type mismatch"""
    config_dict = {
        "models": {
            "default_llm": "test",
            "default_embedding": "test",
            "default_reranker": "test",
            "deploy": [
                {"type": "llm", "name": "model1"},
                "invalid_model_config",  # Here should be a dictionary
            ],
        }
    }

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError):
        config_manager.parse_config(ModelsConfig, "models")


def test_empty_config():
    """Test empty configuration"""
    config_manager = ConfigurationManager()
    with pytest.raises(ValueError):
        config_manager.parse_config(RootConfig)


def test_partial_config():
    """Test partial configuration"""
    config_dict = {
        "system": {
            "language": "en",
            "log_level": "INFO",
            "api_keys": [],
            "encrypt_key": "test",
        }
        # Other sections are missing
    }

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError):
        config_manager.parse_config(RootConfig)


def test_basic_env_var():
    """Test basic environment variable substitution"""
    os.environ["TEST_HOST"] = "test.example.com"
    os.environ["TEST_PORT"] = "5432"

    config_dict = {
        "service": {
            "web": {
                "host": "${env:TEST_HOST}",
                "port": "${env:TEST_PORT}",
                "database": {"type": "sqlite", "path": "db.sqlite3"},
            },
            "model": {
                "controller": {"host": "localhost", "port": 8000},
                "worker": {"host": "localhost", "port": 8001},
                "api": {"host": "localhost", "port": 8002},
            },
        }
    }

    config_manager = ConfigurationManager(config_dict)
    service_config = config_manager.parse_config(ServiceConfig, "service", None)

    assert service_config.web.host == "test.example.com"
    assert service_config.web.port == 5432


def test_env_var_with_default():
    """Test environment variable with default value"""
    config_dict = {
        "system": {
            "language": "${env:LANG:-en}",
            "log_level": "${env:LOG_LEVEL:-INFO}",
            "api_keys": [],
            "encrypt_key": "${env:ENCRYPT_KEY:-https://api.openai.com/v1}",
        }
    }

    # Test with unset environment variables
    if "LANG" in os.environ:
        del os.environ["LANG"]
    if "LOG_LEVEL" in os.environ:
        del os.environ["LOG_LEVEL"]
    if "ENCRYPT_KEY" in os.environ:
        del os.environ["ENCRYPT_KEY"]

    config_manager = ConfigurationManager(config_dict)
    system_config = config_manager.parse_config(SystemConfig, "system", None)

    assert system_config.language == "en"
    assert system_config.log_level == "INFO"
    assert system_config.encrypt_key == "https://api.openai.com/v1"

    # Test with set environment variable
    os.environ["LANG"] = "zh"
    config_manager = ConfigurationManager(config_dict)
    system_config = config_manager.parse_config(SystemConfig, "system", None)
    assert system_config.language == "zh"


def test_nested_env_vars():
    """Test environment variables in nested configuration"""
    os.environ["DB_TYPE"] = "postgres"
    os.environ["DB_PATH"] = "/var/lib/postgres"
    os.environ["MODEL_PORT"] = "9000"

    config_dict = {
        "service": {
            "web": {
                "host": "localhost",
                "port": 8080,
                "database": {"type": "${env:DB_TYPE}", "path": "${env:DB_PATH}"},
            },
            "model": {
                "controller": {"host": "localhost", "port": "${env:MODEL_PORT}"},
                "worker": {"host": "localhost", "port": 8001},
                "api": {"host": "localhost", "port": 8002},
            },
        }
    }

    config_manager = ConfigurationManager(config_dict)
    service_config = config_manager.parse_config(ServiceConfig, "service", None)

    assert service_config.web.database.type == "postgres"
    assert service_config.web.database.path == "/var/lib/postgres"
    assert service_config.model.controller.port == 9000


def test_env_vars_in_list():
    """Test environment variables in list configuration"""
    os.environ["API_KEY_1"] = "key1"
    os.environ["API_KEY_2"] = "key2"

    config_dict = {
        "system": {
            "language": "en",
            "log_level": "INFO",
            "api_keys": ["${env:API_KEY_1}", "${env:API_KEY_2}"],
            "encrypt_key": "test_key",
        }
    }

    config_manager = ConfigurationManager(config_dict)
    system_config = config_manager.parse_config(SystemConfig, "system", None)

    assert "key1" in system_config.api_keys
    assert "key2" in system_config.api_keys
    assert len(system_config.api_keys) == 2


def test_missing_env_var():
    """Test missing environment variable without default"""
    if "MISSING_VAR" in os.environ:
        del os.environ["MISSING_VAR"]

    config_dict = {
        "system": {
            "language": "en",
            "log_level": "INFO",
            "api_keys": [],
            "encrypt_key": "test",
        }
    }

    config_manager = ConfigurationManager(config_dict)
    config_manager.parse_config(SystemConfig, "system", None)


def test_disable_env_vars():
    """Test disabling environment variable resolution"""
    os.environ["TEST_VAR"] = "test_value"

    config_dict = {
        "system": {
            "language": "${env:TEST_VAR}",
            "log_level": "INFO",
            "api_keys": [],
            "encrypt_key": "test",
        }
    }

    config_manager = ConfigurationManager(config_dict, resolve_env_vars=False)
    system_config = config_manager.parse_config(SystemConfig, "system", None)

    assert system_config.language == "${env:TEST_VAR}"


# Datasource configuration classes
@dataclass
class DataSourceConfig(RegisterParameters):
    __type_field__ = "driver"


@dataclass
class TestStorageConfig(RegisterParameters):
    pass


@dataclass
class MySQLDataSource(DataSourceConfig):
    """Test MySQL DataSource Configuration"""

    __type__ = "mysql"
    host: str
    port: int
    database: str
    user: str
    password: str
    charset: str = "utf8mb4"
    pool_size: int = 5
    connection_timeout: int = 30


@dataclass
class SameTestStorageConfig(TestStorageConfig):
    __type__ = "mysql"
    some_host: str


@dataclass
class PostgresDataSource(DataSourceConfig):
    """Test PostgreSQL DataSource Configuration"""

    __type__ = "postgresql"
    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str = "public"
    driver = "postgresql"
    ssl_mode: Optional[str] = None


@dataclass
class ClickHouseDataSource(DataSourceConfig):
    """ClickHouse datasource configuration"""

    __type__ = "clickhouse"
    hosts: List[str]
    database: str
    user: str
    password: str
    driver = "clickhouse"
    secure: bool = False
    settings: Optional[Dict[str, Any]] = None


@dataclass
class MongoDataSourceConfig(DataSourceConfig):
    """MongoDB datasource configuration"""

    uri: str  # mongodb://user:password@host:port
    database: str
    replica_set: Optional[str] = None
    auth_source: Optional[str] = None


@dataclass
class ElasticDataSource(DataSourceConfig):
    """Elasticsearch datasource configuration"""

    __type__ = "elasticsearch"
    hosts: List[str]
    username: Optional[str] = None
    password: Optional[str] = None
    verify_certs: bool = True
    ca_certs: Optional[str] = None
    driver = "elasticsearch"


@dataclass
class DataSourcesConfig:
    """Include multiple data sources"""

    default: str
    sources: Dict[str, DataSourceConfig]


def test_mysql_datasource():
    config_dict = {
        "driver": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "testdb",
        "user": "root",
        "password": "secret",
        "pool_size": 10,
        "charset": "utf8",
    }

    config_manager = ConfigurationManager(config_dict)
    ds_config = config_manager.parse_config(DataSourceConfig)

    assert isinstance(ds_config, MySQLDataSource)
    assert ds_config.host == "localhost"
    assert ds_config.pool_size == 10
    assert ds_config.charset == "utf8"
    assert ds_config.connection_timeout == 30


def test_clickhouse_datasource():
    config_dict = {
        "driver": "clickhouse",
        "hosts": ["ch1:9000", "ch2:9000"],
        "database": "metrics",
        "user": "default",
        "password": "",
        "secure": True,
        "settings": {"insert_quorum": 2, "insert_quorum_timeout": 120},
    }

    config_manager = ConfigurationManager(config_dict)
    ds_config = config_manager.parse_config(DataSourceConfig)

    assert isinstance(ds_config, ClickHouseDataSource)
    assert len(ds_config.hosts) == 2
    assert ds_config.secure is True
    assert ds_config.settings["insert_quorum"] == 2


def test_mongodb_datasource():
    """Test MongoDB datasource (using class name transformed type value)"""
    config_dict = {
        "driver": "mongo",
        "uri": "mongodb://user:pass@localhost:27017",
        "database": "appdb",
        "replica_set": "rs0",
        "auth_source": "admin",
    }

    config_manager = ConfigurationManager(config_dict)
    ds_config = config_manager.parse_config(DataSourceConfig)

    assert isinstance(ds_config, MongoDataSourceConfig)
    assert ds_config.uri == "mongodb://user:pass@localhost:27017"
    assert ds_config.replica_set == "rs0"


def test_multiple_datasources():
    """Test multiple data sources configuration"""
    config_dict = {
        "default": "app_db",
        "sources": {
            "app_db": {
                "driver": "postgresql",
                "host": "postgres.example.com",
                "port": 5432,
                "database": "app",
                "user": "app_user",
                "password": "pass123",
                "schema": "app_schema",
            },
            "metrics_db": {
                "driver": "clickhouse",
                "hosts": ["ch1:9000"],
                "database": "metrics",
                "user": "default",
                "password": "",
                "secure": False,
            },
            "search": {
                "driver": "elasticsearch",
                "hosts": ["es1:9200", "es2:9200"],
                "username": "elastic",
                "password": "secret",
                "verify_certs": False,
            },
        },
    }

    config_manager = ConfigurationManager(config_dict)
    ds_config = config_manager.parse_config(DataSourcesConfig)

    assert ds_config.default == "app_db"
    assert isinstance(ds_config.sources["app_db"], PostgresDataSource)
    assert isinstance(ds_config.sources["metrics_db"], ClickHouseDataSource)
    assert isinstance(ds_config.sources["search"], ElasticDataSource)

    # Verify specific configurations
    pg_config = ds_config.sources["app_db"]
    assert pg_config.schema == "app_schema"
    assert pg_config.driver == "postgresql"

    ch_config = ds_config.sources["metrics_db"]
    assert len(ch_config.hosts) == 1
    assert ch_config.driver == "clickhouse"

    es_config = ds_config.sources["search"]
    assert len(es_config.hosts) == 2
    assert es_config.verify_certs is False
    assert es_config.driver == "elasticsearch"


def test_env_var_datasource():
    import os

    os.environ["DB_HOST"] = "prod.example.com"
    os.environ["DB_PASSWORD"] = "prod_password"

    config_dict = {
        "driver": "postgresql",
        "host": "${env:DB_HOST}",
        "port": 5432,
        "database": "app",
        "user": "app_user",
        "password": "${env:DB_PASSWORD}",
        "schema": "prod_schema",
    }

    config_manager = ConfigurationManager(config_dict)
    ds_config = config_manager.parse_config(DataSourceConfig)

    assert isinstance(ds_config, PostgresDataSource)
    assert ds_config.host == "prod.example.com"
    assert ds_config.password == "prod_password"


def test_invalid_driver():
    """Test invalid driver type"""
    config_dict = {"driver": "invalid_db", "host": "localhost", "port": 1234}

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError):
        config_manager.parse_config(DataSourceConfig)


def test_optional_datasource_fields():
    """Test optional fields in datasource configuration"""
    config_dict = {
        "driver": "elasticsearch",
        "hosts": ["es1:9200"],
        # not providing username and password
    }

    config_manager = ConfigurationManager(config_dict)
    ds_config = config_manager.parse_config(DataSourceConfig)

    assert isinstance(ds_config, ElasticDataSource)
    assert ds_config.username is None
    assert ds_config.verify_certs is True


def test_independent_type_registries():
    """Test that different base classes maintain independent type registries"""
    # Get subclasses from different base classes using same type value
    mysql_ds = DataSourceConfig.get_subclass("mysql")
    mysql_storage = TestStorageConfig.get_subclass("mysql")

    # Verify they are different classes
    assert mysql_ds is not mysql_storage
    assert mysql_ds is MySQLDataSource
    assert mysql_storage is SameTestStorageConfig

    # Verify each base class has its own registry
    assert hasattr(DataSourceConfig, "_type_registry")
    assert hasattr(TestStorageConfig, "_type_registry")
    assert DataSourceConfig._type_registry is not TestStorageConfig._type_registry


def test_datasource_registry_isolation():
    """Test that DataSourceConfig registry contains only its subclasses"""
    registry = getattr(DataSourceConfig, "_type_registry", {})

    # Check for expected classes
    assert "mysql" in registry
    assert "postgresql" in registry
    assert "clickhouse" in registry
    assert "elasticsearch" in registry

    # Verify it doesn't contain classes from TestStorageConfig
    all_values = list(registry.values())
    assert SameTestStorageConfig not in all_values


def test_storage_registry_isolation():
    """Test that TestStorageConfig registry contains only its subclasses"""
    registry = getattr(TestStorageConfig, "_type_registry", {})

    # Check for expected classes
    assert "mysql" in registry
    assert SameTestStorageConfig in registry.values()

    # Verify it doesn't contain classes from DataSourceConfig
    all_values = list(registry.values())
    assert MySQLDataSource not in all_values
    assert PostgresDataSource not in all_values


def test_independent_configs():
    """Test that configurations can be parsed independently for different base
    classes
    """
    # Test DataSourceConfig parsing
    ds_config_dict = {
        "driver": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "testdb",
        "user": "root",
        "password": "secret",
    }

    ds_config_manager = ConfigurationManager(ds_config_dict)
    ds_config = ds_config_manager.parse_config(DataSourceConfig)
    assert isinstance(ds_config, MySQLDataSource)

    # Test TestStorageConfig parsing
    storage_config_dict = {"type": "mysql", "some_host": "storage.example.com"}

    storage_config_manager = ConfigurationManager(storage_config_dict)
    storage_config = storage_config_manager.parse_config(TestStorageConfig)
    assert isinstance(storage_config, SameTestStorageConfig)
    assert storage_config.some_host == "storage.example.com"


def test_type_field_customization():
    """Test that different base classes can use different type field names"""
    # DataSourceConfig uses "driver" as type field
    ds_config_dict = {
        "driver": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "testdb",
        "user": "root",
        "password": "secret",
    }

    ds_config_manager = ConfigurationManager(ds_config_dict)
    ds_config = ds_config_manager.parse_config(DataSourceConfig)
    assert isinstance(ds_config, MySQLDataSource)

    # TestStorageConfig uses default "type" field
    storage_config_dict = {"type": "mysql", "some_host": "storage.example.com"}

    storage_config_manager = ConfigurationManager(storage_config_dict)
    storage_config = storage_config_manager.parse_config(TestStorageConfig)
    assert isinstance(storage_config, SameTestStorageConfig)


def test_register_subclass_method():
    """Test manual registration of subclasses to different registries"""

    @dataclass
    class NewDataSource(DataSourceConfig):
        host: str
        port: int

    @dataclass
    class NewStorage(TestStorageConfig):
        path: str

    # Register to different base classes
    DataSourceConfig.register_subclass("new", NewDataSource)
    TestStorageConfig.register_subclass("new", NewStorage)

    # Verify they are registered in correct registries
    assert DataSourceConfig.get_subclass("new") is NewDataSource
    assert TestStorageConfig.get_subclass("new") is NewStorage
    assert DataSourceConfig.get_subclass("new") is not TestStorageConfig.get_subclass(
        "new"
    )


def test_invalid_type_values():
    """Test error handling for invalid type values in different registries"""
    # Test invalid DataSourceConfig type
    ds_config_dict = {"driver": "invalid_type", "host": "localhost"}

    ds_config_manager = ConfigurationManager(ds_config_dict)
    with pytest.raises(ValueError, match="Unknown type value: invalid_type"):
        ds_config_manager.parse_config(DataSourceConfig)

    # Test invalid TestStorageConfig type
    storage_config_dict = {"type": "invalid_type", "some_host": "example.com"}

    storage_config_manager = ConfigurationManager(storage_config_dict)
    with pytest.raises(ValueError, match="Unknown type value: invalid_type"):
        storage_config_manager.parse_config(TestStorageConfig)


@dataclass
class TestDbConfig:
    host: str
    port: int
    username: str
    password: str
    max_connections: int = 10


@dataclass
class TestAppConfig:
    name: str
    database: TestDbConfig
    debug: bool = False
    allowed_origins: List[str] = field(default_factory=list)


class EnvVarSetHook:
    """A hook that sets environment variables based on initialization parameters"""

    def __init__(self, env_vars: Dict[str, str] = None):
        """
        Args:
            env_vars: Dictionary of environment variables to set.
                     Key is the environment variable name, value is its value.
        """
        self.env_vars = env_vars or {}
        self._original_env = {}

    def __call__(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Set environment variables and return the config unchanged"""
        # Save original environment variables that we're going to override
        self._original_env = {
            key: os.environ.get(key) for key in self.env_vars if key in os.environ
        }

        # Set new environment variables
        for key, value in self.env_vars.items():
            os.environ[key] = str(value)

        return config

    def cleanup(self):
        """Restore original environment variables"""
        # Remove variables that weren't present before
        for key in self.env_vars:
            if key not in self._original_env:
                os.environ.pop(key, None)

        # Restore original values
        for key, value in self._original_env.items():
            if value is not None:
                os.environ[key] = value


class ConfigValidationHook:
    """A hook that validates configuration values against rules"""

    def __init__(self, rules: Dict[str, Dict[str, Any]] = None):
        """
        Args:
            rules: Dictionary of validation rules.
                  Key is the field path, value is a dict with validation rules:
                  - max: maximum value for numbers
                  - min: minimum value for numbers
                  - length_max: maximum length for strings
                  - prefix: required prefix for strings
        """
        self.rules = rules or {}

    def _convert_value(self, value: Any, rule: Dict[str, Any]) -> Any:
        """Convert value to appropriate type based on rule"""
        if any(key in rule for key in ["max", "min"]):
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        return value

    def __call__(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Validate configuration values against rules"""

        def validate_value(path: str, value: Any, rule: Dict[str, Any]):
            # Convert value if necessary
            value = self._convert_value(value, rule)

            for rule_name, rule_value in rule.items():
                if not isinstance(value, (int, float)) and rule_name in ["min", "max"]:
                    continue  # Skip numeric validation for non-numeric values

                if rule_name == "max" and value > rule_value:
                    raise ValueError(
                        f"Value {value} at {path} exceeds maximum {rule_value}"
                    )
                elif rule_name == "min" and value < rule_value:
                    raise ValueError(
                        f"Value {value} at {path} below minimum {rule_value}"
                    )
                elif rule_name == "length_max" and len(str(value)) > rule_value:
                    raise ValueError(
                        f"Value at {path} exceeds maximum length {rule_value}"
                    )
                elif rule_name == "prefix" and not str(value).startswith(rule_value):
                    raise ValueError(
                        f"Value at {path} must start with '{rule_value}', found {value}"
                    )

        for path, rule in self.rules.items():
            keys = path.split(".")
            current = config
            for key in keys[:-1]:
                current = current.get(key, {})
            if keys[-1] in current:
                validate_value(path, current[keys[-1]], rule)

        return config


def get_hook_path(cls: type) -> str:
    """Get the full module path for a class"""
    module = sys.modules[cls.__module__]
    return f"{module.__name__}.{cls.__name__}"


def test_env_var_set_hook():
    """Test basic environment variable setting functionality"""
    config_dict = {
        "app": {
            "name": "test-app",
            "database": {
                "host": "${env:TEST_DB_HOST}",
                "port": "${env:TEST_DB_PORT}",
                "username": "test-user",
                "password": "${env:TEST_DB_PASSWORD}",
                "max_connections": 20,
            },
            "hooks": [
                {
                    "path": get_hook_path(EnvVarSetHook),
                    "enabled": True,
                    "init_params": {
                        "env_vars": {
                            "TEST_DB_HOST": "test-host",
                            "TEST_DB_PORT": "5432",
                            "TEST_DB_PASSWORD": "test-password",
                        }
                    },
                }
            ],
        }
    }

    config_manager = ConfigurationManager(config_dict)
    service_config = config_manager.parse_config(TestAppConfig, "app", None, "hooks")

    assert service_config.database.host == "test-host"
    assert service_config.database.port == 5432
    assert service_config.database.password == "test-password"


def test_config_validation_failure():
    """Test ConfigValidationHook with invalid values"""
    config_dict = {
        "app": {
            "name": "invalid-name",
            "database": {
                "host": "localhost",
                "port": 80,  # Invalid port number
                "username": "test-user",
                "password": "secret",
            },
            "hooks": [
                {
                    "path": get_hook_path(ConfigValidationHook),
                    "enabled": True,
                    "init_params": {
                        "rules": {"database.port": {"min": 1024, "max": 65535}}
                    },
                }
            ],
        }
    }

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError, match="Value .* below minimum 1024"):
        config_manager.parse_config(TestAppConfig, "app", None, "hooks")


def test_env_var_set_hook_disabled():
    """Test that disabled EnvVarSetHook doesn't set environment variables"""
    if "TEST_APP_NAME" in os.environ:
        del os.environ["TEST_APP_NAME"]

    config_dict = {
        "app": {
            "name": "${env:TEST_APP_NAME:-default-name}",  # Provide default value
            "database": {
                "host": "localhost",
                "port": 5432,
                "username": "test-user",
                "password": "secret",
            },
            "hooks": [
                {
                    "path": get_hook_path(EnvVarSetHook),
                    "enabled": False,
                    "init_params": {"env_vars": {"TEST_APP_NAME": "test-app"}},
                }
            ],
        }
    }

    config_manager = ConfigurationManager(config_dict)
    service_config = config_manager.parse_config(TestAppConfig, "app", None, "hooks")

    # Since hook is disabled, environment variable shouldn't be set
    assert "TEST_APP_NAME" not in os.environ
    assert service_config.name == "default-name"  # Use default value


# Test Dataclasses with custom from_dict methods
@dataclass
class CustomUser:
    name: str
    age: int
    email: Optional[str] = None

    @classmethod
    def _from_dict_(cls, data: Dict, prepare_data_func, converter) -> "CustomUser":
        # Custom logic to create instance
        name = data.get("full_name", "").strip()  # Use different field name
        age = converter(data.get("user_age", 0), int)  # Use different field name
        email = data.get("email")
        return cls(name=name, age=age, email=email)


@dataclass
class ExtCustomUser:
    name: str
    age: int
    email: Optional[str] = None

    @classmethod
    def _from_dict_(cls, data: Dict, prepare_data_func, converter) -> "CustomUser":
        real_data = prepare_data_func(cls, data)
        return cls(**real_data)


@dataclass
class CustomAddress:
    street: str
    city: str
    country: str = "Unknown"

    @classmethod
    def _from_dict_(cls, data: Dict, prepare_data_func, converter) -> "CustomAddress":
        # Combine street number and name
        street_num = data.get("street_number", "")
        street_name = data.get("street_name", "")
        street = f"{street_num} {street_name}".strip()
        return cls(
            street=street,
            city=data.get("city", ""),
            country=data.get("country", "Unknown"),
        )


@dataclass
class CustomProfile:
    user: CustomUser
    address: CustomAddress
    tags: List[str] = field(default_factory=list)

    @classmethod
    def _from_dict_(cls, data: Dict, prepare_data_func, converter) -> "CustomProfile":
        # Convert nested objects using the converter
        user_data = data.get("user_info", {})  # Different field name
        address_data = data.get("address_info", {})  # Different field name

        return cls(
            user=converter(user_data, CustomUser),
            address=converter(address_data, CustomAddress),
            tags=data.get("tags", []),
        )


def test_basic_custom_from_dict():
    """Test basic custom from_dict implementation"""
    config_dict = {
        "full_name": "John Doe",
        "user_age": "30",
        "email": "john@example.com",
    }

    config_manager = ConfigurationManager(config_dict)
    user_config = config_manager.parse_config(CustomUser)

    assert user_config.name == "John Doe"
    assert user_config.age == 30
    assert user_config.email == "john@example.com"


def test_basic_ext_custom_from_dict():
    """Test basic custom from_dict implementation"""
    config_dict = {
        "name": "John Doe",
        "age": 30,
        "email": "john@example.com",
        "other_field": "extra",  # Extra field should be ignored
    }
    config_manager = ConfigurationManager(config_dict)
    user_config = config_manager.parse_config(ExtCustomUser)
    assert user_config.name == "John Doe"


def test_nested_custom_from_dict():
    """Test nested objects with custom from_dict methods"""
    config_dict = {
        "user_info": {
            "full_name": "Jane Smith",
            "user_age": "25",
            "email": "jane@example.com",
        },
        "address_info": {
            "street_number": "123",
            "street_name": "Main St",
            "city": "Boston",
            "country": "USA",
        },
        "tags": ["developer", "python"],
    }

    config_manager = ConfigurationManager(config_dict)
    profile_config = config_manager.parse_config(CustomProfile)

    assert profile_config.user.name == "Jane Smith"
    assert profile_config.user.age == 25
    assert profile_config.address.street == "123 Main St"
    assert profile_config.tags == ["developer", "python"]


def test_custom_from_dict_with_missing_fields():
    """Test custom from_dict with missing optional fields"""
    config_dict = {
        "full_name": "John Doe",
        "user_age": "30",
        # email is missing
    }

    config_manager = ConfigurationManager(config_dict)
    user_config = config_manager.parse_config(CustomUser)

    assert user_config.name == "John Doe"
    assert user_config.age == 30
    assert user_config.email is None


def test_custom_from_dict_with_default_values():
    """Test custom from_dict with default values"""
    config_dict = {
        "street_number": "456",
        "street_name": "Oak Avenue",
        "city": "Chicago",
        # country will use default value
    }

    config_manager = ConfigurationManager(config_dict)
    address_config = config_manager.parse_config(CustomAddress)

    assert address_config.street == "456 Oak Avenue"
    assert address_config.city == "Chicago"
    assert address_config.country == "Unknown"


def test_invalid_custom_from_dict():
    """Test custom from_dict with invalid data type"""
    config_dict = {
        "full_name": "John Doe",
        "user_age": "invalid_age",  # This should raise an error
        "email": "john@example.com",
    }

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError):
        config_manager.parse_config(CustomUser)


@dataclass
class PartialCustomConfig:
    name: str
    value: int

    @classmethod
    def _from_dict_(
        cls, data: Dict, prepare_data_func, converter
    ) -> "PartialCustomConfig":
        # Demonstrate using converter for specific fields
        return cls(
            name=data.get("name", ""), value=converter(data.get("value", 0), int)
        )


def test_partial_custom_conversion():
    """Test custom from_dict with partial custom conversion"""
    config_dict = {"name": "test", "value": "42"}  # String that needs conversion

    config_manager = ConfigurationManager(config_dict)
    config = config_manager.parse_config(PartialCustomConfig)

    assert config.name == "test"
    assert config.value == 42
    assert isinstance(config.value, int)


@dataclass
class BaseDbConfig:
    host: str
    port: int

    @classmethod
    def _parse_class_(cls, data: Dict) -> Optional[Type["BaseDbConfig"]]:
        db_type = data.get("type", "").lower()
        if db_type == "mysql":
            return MySQLConfig
        elif db_type == "postgres":
            return PostgresConfig
        elif db_type == "mongodb":
            return MongoDBConfig
        return None


@dataclass
class MySQLConfig(BaseDbConfig):
    database: str
    user: str
    password: str
    charset: str = "utf8mb4"


@dataclass
class PostgresConfig(BaseDbConfig):
    database: str
    user: str
    password: str
    schema: str = "public"


@dataclass
class MongoDBConfig(BaseDbConfig):
    database: str
    user: str
    password: str
    replica_set: Optional[str] = None


# Model configurations for different model types
@dataclass
class BaseModelConfig:
    name: str
    version: str

    @classmethod
    def _parse_class_(cls, data: Dict) -> Optional[Type["BaseModelConfig"]]:
        if "gpu_memory" in data:
            return GPUModelConfig
        elif "quantization" in data:
            return QuantizedModelConfig
        return None


@dataclass
class GPUModelConfig(BaseModelConfig):
    gpu_memory: int
    batch_size: int


@dataclass
class QuantizedModelConfig(BaseModelConfig):
    quantization: str
    threads: int


# Test cases
def test_basic_parse_class():
    """Test basic class parsing based on type field"""
    config_dict = {
        "type": "mysql",
        "host": "localhost",
        "port": 3306,
        "database": "testdb",
        "user": "root",
        "password": "secret",
    }

    config_manager = ConfigurationManager(config_dict)
    db_config = config_manager.parse_config(BaseDbConfig)

    assert isinstance(db_config, MySQLConfig)
    assert db_config.host == "localhost"
    assert db_config.port == 3306
    assert db_config.charset == "utf8mb4"


def test_parse_class_with_feature_detection():
    """Test class parsing based on feature detection"""
    config_dict = {
        "name": "gpt-4",
        "version": "1.0",
        "gpu_memory": 16384,
        "batch_size": 32,
    }

    config_manager = ConfigurationManager(config_dict)
    model_config = config_manager.parse_config(BaseModelConfig)

    assert isinstance(model_config, GPUModelConfig)
    assert model_config.gpu_memory == 16384
    assert model_config.batch_size == 32


def test_parse_class_fallback():
    """Test fallback when no specific class is selected"""
    config_dict = {"type": "unknown", "host": "localhost", "port": 5432}

    config_manager = ConfigurationManager(config_dict)
    db_config = config_manager.parse_config(BaseDbConfig)

    assert isinstance(db_config, BaseDbConfig)
    assert not isinstance(db_config, (MySQLConfig, PostgresConfig, MongoDBConfig))
    assert db_config.host == "localhost"
    assert db_config.port == 5432


def test_parse_class_with_defaults():
    """Test class parsing with default values"""
    config_dict = {
        "type": "postgres",
        "host": "localhost",
        "port": 5432,
        "database": "testdb",
        "user": "postgres",
        "password": "secret",
    }

    config_manager = ConfigurationManager(config_dict)
    db_config = config_manager.parse_config(BaseDbConfig)

    assert isinstance(db_config, PostgresConfig)
    assert db_config.schema == "public"  # Default value


def test_parse_class_with_optional_fields():
    """Test class parsing with optional fields"""
    config_dict = {
        "type": "mongodb",
        "host": "localhost",
        "port": 27017,
        "database": "testdb",
        "user": "admin",
        "password": "secret",
        # replica_set is optional
    }

    config_manager = ConfigurationManager(config_dict)
    db_config = config_manager.parse_config(BaseDbConfig)

    assert isinstance(db_config, MongoDBConfig)
    assert db_config.replica_set is None


@dataclass
class NestedConfig:
    db: BaseDbConfig
    model: BaseModelConfig

    @classmethod
    def _parse_class_(cls, data: Dict) -> Optional[Type["NestedConfig"]]:
        # Demonstrate that parse_class can also be used in nested configurations
        if data.get("environment") == "production":
            return ProductionConfig
        return None


@dataclass
class ProductionConfig(NestedConfig):
    replicas: int
    monitoring: bool = True


def test_nested_parse_class():
    """Test nested configurations with parse_class"""
    config_dict = {
        "environment": "production",
        "replicas": 3,
        "db": {
            "type": "mysql",
            "host": "prod-db",
            "port": 3306,
            "database": "proddb",
            "user": "admin",
            "password": "secret",
        },
        "model": {
            "name": "gpt-4",
            "version": "1.0",
            "quantization": "int8",
            "threads": 4,
        },
    }

    config_manager = ConfigurationManager(config_dict)
    config = config_manager.parse_config(NestedConfig)

    assert isinstance(config, ProductionConfig)
    assert isinstance(config.db, MySQLConfig)
    assert isinstance(config.model, QuantizedModelConfig)
    assert config.replicas == 3
    assert config.monitoring is True  # Default value


def test_multiple_parse_class_conditions():
    """Test multiple conditions in parse_class"""

    @dataclass
    class MultiConditionConfig:
        name: str

        @classmethod
        def _parse_class_(cls, data: Dict) -> Optional[Type["MultiConditionConfig"]]:
            if "gpu" in data and data.get("distributed", False):
                return DistributedGPUConfig
            elif "gpu" in data:
                return SingleGPUConfig
            elif data.get("distributed", False):
                return DistributedCPUConfig
            return None

    @dataclass
    class DistributedGPUConfig(MultiConditionConfig):
        gpu: int
        nodes: int

    @dataclass
    class SingleGPUConfig(MultiConditionConfig):
        gpu: int

    @dataclass
    class DistributedCPUConfig(MultiConditionConfig):
        nodes: int

    # Test different combinations
    config_dict = {"name": "test", "gpu": 2, "distributed": True, "nodes": 4}

    config_manager = ConfigurationManager(config_dict)
    config = config_manager.parse_config(MultiConditionConfig)

    assert isinstance(config, DistributedGPUConfig)
    assert config.gpu == 2
    assert config.nodes == 4


def test_parse_class_chaining():
    """Test chaining of parse_class with from_dict"""

    @dataclass
    class ChainedConfig:
        value: str

        @classmethod
        def _parse_class_(cls, data: Dict) -> Optional[Type["ChainedConfig"]]:
            if data.get("type") == "special":
                return SpecialChainedConfig
            return None

        @classmethod
        def _from_dict_(
            cls, data: Dict, prepare_data_func, converter
        ) -> "ChainedConfig":
            return cls(value=data.get("value", "").upper())

    @dataclass
    class SpecialChainedConfig(ChainedConfig):
        extra: str = "special"

    config_dict = {"type": "special", "value": "test"}

    config_manager = ConfigurationManager(config_dict)
    config = config_manager.parse_config(ChainedConfig)

    assert isinstance(config, SpecialChainedConfig)
    assert config.value == "TEST"  # Transformed by _from_dict_
    assert config.extra == "special"


@pytest.fixture(autouse=True)
def cleanup_env_vars():
    """Automatically cleanup environment variables after each test"""
    test_vars = [
        "TEST_DB_HOST",
        "TEST_DB_PORT",
        "TEST_DB_PASSWORD",
        "TEST_APP_NAME",
        "TEST_EXISTING_VAR",
    ]

    # Keep original values for existing variables
    original_values = {
        var: os.environ.get(var) for var in test_vars if var in os.environ
    }

    yield

    for var in test_vars:
        if var not in original_values:
            os.environ.pop(var, None)
        else:
            os.environ[var] = original_values[var]


def test_basic_config_description():
    """Test basic configuration description parsing"""
    descriptions = ConfigurationManager.parse_description(SystemConfig)

    assert len(descriptions) == 4

    # Test language field
    lang_desc = next(d for d in descriptions if d.param_name == "language")
    assert lang_desc.param_type == "string"
    assert lang_desc.required is True
    assert not lang_desc.is_array
    assert lang_desc.nested_fields is None

    # Test api_keys field
    api_keys_desc = next(d for d in descriptions if d.param_name == "api_keys")
    assert api_keys_desc.param_type == "string"  # 元素类型是 string
    assert api_keys_desc.is_array is True  # 标记为数组

    # Test log_level field
    log_level_desc = next(d for d in descriptions if d.param_name == "log_level")
    assert log_level_desc.param_type == "string"
    assert not log_level_desc.is_array


def test_list_config_description():
    """Test configuration with list fields"""
    descriptions = ConfigurationManager.parse_description(RagConfig)

    # Test chunk array field
    chunk_desc = next(d for d in descriptions if d.param_name == "chunk")
    assert chunk_desc.is_array is True  # 是数组
    assert chunk_desc.param_type == "ChunkConfig"  # 元素类型是 ChunkConfig

    # Verify nested chunk config
    assert chunk_desc.nested_fields is not None
    chunk_fields = chunk_desc.nested_fields["chunkconfig"]
    chunk_type_desc = next(d for d in chunk_fields if d.param_name == "type")
    assert chunk_type_desc.param_type == "string"
    assert not chunk_type_desc.is_array


def test_app_config_lists():
    """Test AppConfig with nested list fields"""
    descriptions = ConfigurationManager.parse_description(AppConfig)

    # Check configs field which is List[AppConfigItem]
    configs_desc = next(d for d in descriptions if d.param_name == "configs")
    assert configs_desc.is_array is True
    assert configs_desc.param_type == "AppConfigItem"  # 元素类型是 AppConfigItem

    # Check nested AppConfigItem fields
    assert configs_desc.nested_fields is not None
    config_item_fields = configs_desc.nested_fields["appconfigitem"]
    name_desc = next(d for d in config_item_fields if d.param_name == "name")
    assert name_desc.param_type == "string"
    assert not name_desc.is_array


def test_datasource_arrays():
    """Test arrays in datasource configurations"""
    descriptions = ConfigurationManager.parse_description(ClickHouseDataSource)

    # Test hosts field which is List[str]
    hosts_desc = next(d for d in descriptions if d.param_name == "hosts")
    assert hosts_desc.is_array is True
    assert hosts_desc.param_type == "string"  # 元素类型是 string

    # Test settings field which is Dict[str, Any]
    settings_desc = next(d for d in descriptions if d.param_name == "settings")
    assert not settings_desc.is_array
    assert settings_desc.param_type == "object"


def test_model_config_lists():
    """Test model configuration with deployment lists"""
    descriptions = ConfigurationManager.parse_description(ModelsConfig)

    # Test deploy field which is List[ModelDeployConfig]
    deploy_desc = next(d for d in descriptions if d.param_name == "deploy")
    assert deploy_desc.is_array is True
    assert deploy_desc.param_type == "ModelDeployConfig"  # 元素类型是 ModelDeployConfig

    # Check nested ModelDeployConfig fields
    assert deploy_desc.nested_fields is not None
    deploy_fields = deploy_desc.nested_fields["modeldeployconfig"]
    type_desc = next(d for d in deploy_fields if d.param_name == "type")
    assert type_desc.param_type == "string"
    assert not type_desc.is_array
