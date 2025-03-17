"""Neo4j store."""

import logging
from dataclasses import dataclass

from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig

logger = logging.getLogger(__name__)


@dataclass
class Neo4jStoreConfig(GraphStoreConfig):
    """Neo4j store config."""

    __type__ = "neo4j"


class Neo4jStore(GraphStoreBase):
    """Neo4j graph store."""

    # todo: add neo4j implementation
