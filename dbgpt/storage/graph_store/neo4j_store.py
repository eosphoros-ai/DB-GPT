"""Neo4j store."""
import logging

from dbgpt._private.pydantic import ConfigDict
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig

logger = logging.getLogger(__name__)


class Neo4jStoreConfig(GraphStoreConfig):
    """Neo4j store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Neo4jStore(GraphStoreBase):
    """Neo4j graph store."""

    # todo: add neo4j implementation
