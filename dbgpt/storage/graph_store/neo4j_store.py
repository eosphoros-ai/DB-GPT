"""Neo4j vector store."""
import logging

from .base import GraphStoreBase

logger = logging.getLogger(__name__)


class Neo4jStore(GraphStoreBase):
    """Neo4j vector store."""
