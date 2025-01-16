import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pytest

from ...configure.manager import ConfigurationManager


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
    system_config = config_manager.parse_config(SystemConfig, "system")

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
    service_config = config_manager.parse_config(ServiceConfig, "service")

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
    models_config = config_manager.parse_config(ModelsConfig, "models")

    assert models_config.default_llm == "glm-4-9b-chat"
    assert len(models_config.deploy) == 2
    assert models_config.deploy[0].type == "llm"
    assert models_config.deploy[1].inference_type == "proxyllm"


def test_optional_fields():
    config_dict = {"models": {"deploy": [{"type": "llm", "name": "model1"}]}}

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError, match="Missing required field"):
        config_manager.parse_config(ModelsConfig, "models")


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
    config_dict = {}
    config_manager = ConfigurationManager(config_dict)

    with pytest.raises(ValueError, match="Configuration section not found"):
        config_manager.parse_config(SystemConfig, "system")


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
        config_manager.parse_config(ServiceConfig, "service")


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
    models_config = config_manager.parse_config(ModelsConfig, "models")

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
    app_config = config_manager.parse_config(AppConfig, "app")
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
    rag_config = config_manager.parse_config(RagConfig, "rag")
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
    service_config = config_manager.parse_config(ServiceConfig, "service")

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
        config_manager.parse_config(ServiceConfig, "service")

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
    service_config = config_manager.parse_config(ServiceConfig, "service")

    assert service_config.web.host == "test.example.com"
    assert service_config.web.port == 5432


def test_env_var_with_default():
    """Test environment variable with default value"""
    config_dict = {
        "system": {
            "language": "${env:LANG:-en}",
            "log_level": "${env:LOG_LEVEL:-INFO}",
            "api_keys": [],
            "encrypt_key": "${env:ENCRYPT_KEY:-default_key}",
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
    system_config = config_manager.parse_config(SystemConfig, "system")

    assert system_config.language == "en"
    assert system_config.log_level == "INFO"
    assert system_config.encrypt_key == "default_key"

    # Test with set environment variable
    os.environ["LANG"] = "zh"
    config_manager = ConfigurationManager(config_dict)
    system_config = config_manager.parse_config(SystemConfig, "system")
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
    service_config = config_manager.parse_config(ServiceConfig, "service")

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
    system_config = config_manager.parse_config(SystemConfig, "system")

    assert "key1" in system_config.api_keys
    assert "key2" in system_config.api_keys
    assert len(system_config.api_keys) == 2


def test_missing_env_var():
    """Test missing environment variable without default"""
    if "MISSING_VAR" in os.environ:
        del os.environ["MISSING_VAR"]

    config_dict = {
        "system": {
            "language": "${env:MISSING_VAR}",
            "log_level": "INFO",
            "api_keys": [],
            "encrypt_key": "test",
        }
    }

    config_manager = ConfigurationManager(config_dict)
    with pytest.raises(ValueError, match="Environment variable MISSING_VAR not found"):
        config_manager.parse_config(SystemConfig, "system")


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
    system_config = config_manager.parse_config(SystemConfig, "system")

    assert system_config.language == "${env:TEST_VAR}"
