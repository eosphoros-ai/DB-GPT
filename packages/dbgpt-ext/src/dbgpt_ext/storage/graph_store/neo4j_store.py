"""Neo4j store."""

import logging
import os
from dataclasses import dataclass, field
from typing import List

from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import GraphElemType
from dbgpt.util.i18n_utils import _
from dbgpt_ext.datasource.conn_neo4j import Neo4jConnector

logger = logging.getLogger(__name__)


@register_resource(
    _("Neo4j Graph Config"),
    "neo4j_config",
    category=ResourceCategory.KNOWLEDGE_GRAPH,
    description=_("Neo4j config."),
    parameters=[
        Parameter.build_from(
            _("host"),
            "host",
            str,
            optional=True,
            default="127.0.0.1",
            description=_("Neo4j host"),
        ),
        Parameter.build_from(
            _("port"),
            "port",
            int,
            optional=True,
            default=7687,
            description=_("Neo4j port"),
        ),
        Parameter.build_from(
            _("username"),
            "username",
            str,
            optional=True,
            default="neo4j",
            description=_("Neo4j username"),
        ),
        Parameter.build_from(
            _("password"),
            "password",
            str,
            optional=True,
            default="neo4j",
            description=_("Neo4j password"),
        ),
        Parameter.build_from(
            _("database"),
            "database",
            str,
            optional=True,
            default="neo4j",
            description=_("Neo4j database name"),
        ),
    ],
)
@dataclass
class Neo4jStoreConfig(GraphStoreConfig):
    """Neo4j store config."""

    __type__ = "neo4j"

    host: str = field(
        default="127.0.0.1",
        metadata={
            "description": "Neo4j host",
        },
    )
    port: int = field(
        default=7687,
        metadata={
            "description": "Neo4j port",
        },
    )
    username: str = field(
        default="neo4j",
        metadata={
            "description": "login username",
        },
    )
    password: str = field(
        default="neo4j",
        metadata={
            "description": "login password",
        },
    )
    database: str = field(
        default="neo4j",
        metadata={
            "description": "Neo4j database name",
        },
    )
    vertex_type: str = field(
        default=GraphElemType.ENTITY.value,
        metadata={
            "description": "The type of vertex, `entity` by default.",
        },
    )
    document_type: str = field(
        default=GraphElemType.DOCUMENT.value,
        metadata={
            "description": "The type of document vertex, `document` by default.",
        },
    )
    chunk_type: str = field(
        default=GraphElemType.CHUNK.value,
        metadata={
            "description": "The type of chunk vertex, `chunk` by default.",
        },
    )
    edge_type: str = field(
        default=GraphElemType.RELATION.value,
        metadata={
            "description": "The type of relation edge, `relation` by default.",
        },
    )
    include_type: str = field(
        default=GraphElemType.INCLUDE.value,
        metadata={
            "description": "The type of include edge, `include` by default.",
        },
    )
    next_type: str = field(
        default=GraphElemType.NEXT.value,
        metadata={
            "description": "The type of next edge, `next` by default.",
        },
    )
    enable_summary: bool = field(
        default=True,
        metadata={
            "description": "Enable graph community summary or not.",
        },
    )
    enable_similarity_search: bool = field(
        default=False,
        metadata={
            "description": "Enable the similarity search or not",
        },
    )


class Neo4jStore(GraphStoreBase):
    """Neo4j graph store."""

    def __init__(self, config: Neo4jStoreConfig) -> None:
        """Initialize the Neo4jStore with connection details."""
        self._config = config
        self._host = config.host or os.getenv("NEO4J_HOST", "127.0.0.1")
        self._port = int(config.port or os.getenv("NEO4J_PORT", "7687"))
        self._username = config.username or os.getenv("NEO4J_USER", "neo4j")
        self._password = config.password or os.getenv("NEO4J_PASSWORD", "neo4j")
        self._database = config.database or os.getenv("NEO4J_DATABASE", "neo4j")
        self.enable_summary = config.enable_summary or (
            os.getenv("GRAPH_COMMUNITY_SUMMARY_ENABLED", "").lower() == "true"
        )
        self.enable_similarity_search = config.enable_similarity_search or (
            os.getenv("SIMILARITY_SEARCH_ENABLED", "").lower() == "true"
        )

        self._graph_name = config.name

        self.conn = Neo4jConnector.from_uri_db(
            host=self._host,
            port=self._port,
            user=self._username,
            pwd=self._password,
            db_name=self._database,  # Use database field instead of config.name
        )

    def get_config(self) -> Neo4jStoreConfig:
        """Get the Neo4j store config."""
        return self._config

    def is_exist(self, name: str) -> bool:
        """Check if graph (database) exists in Neo4j.
        
        Args:
            name: Database name to check
            
        Returns:
            bool: True if database exists
        """
        return self.conn.is_exist(name)
