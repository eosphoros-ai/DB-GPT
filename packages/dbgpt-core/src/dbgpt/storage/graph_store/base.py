"""Graph store base class."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from dbgpt.util import BaseParameters, RegisterParameters

logger = logging.getLogger(__name__)


@dataclass
class GraphStoreConfig(BaseParameters, RegisterParameters):
    """Graph store config."""

    __cfg_type__ = "graph_store"

    # name: str = Field(
    #     default="dbgpt_collection",
    #     description="The name of graph store, inherit from index store.",
    # )
    # embedding_fn: Optional[Embeddings] = Field(
    #     default=None,
    #     description="The embedding function of graph store, optional.",
    # )
    # enable_summary: bool = Field(
    #     default=False,
    #     description="Enable graph community summary or not.",
    # )
    # enable_similarity_search: bool = Field(
    #     default=False,
    #     description="Enable similarity search or not.",
    # )


class GraphStoreBase(ABC):
    """Graph store base class."""

    def __init__(self, config: GraphStoreConfig):
        """Initialize graph store."""
        self._config = config
        self._conn = None
        self.enable_summary = config.enable_summary
        self.enable_similarity_search = config.enable_similarity_search

    @abstractmethod
    def get_config(self) -> GraphStoreConfig:
        """Get the graph store config."""

    def is_exist(self, name) -> bool:
        """Check Graph Name is Exist."""
        raise NotImplementedError
