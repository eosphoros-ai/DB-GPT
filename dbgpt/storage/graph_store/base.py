"""Graph store base class."""

import logging
from abc import ABC, abstractmethod
from typing import Optional

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field
from dbgpt.core import Embeddings

logger = logging.getLogger(__name__)


class GraphStoreConfig(BaseModel):
    """Graph store config."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="allow")

    name: str = Field(
        default="dbgpt_collection",
        description="The name of graph store, inherit from index store.",
    )
    embedding_fn: Optional[Embeddings] = Field(
        default=None,
        description="The embedding function of graph store, optional.",
    )
    enable_summary: bool = Field(
        default=False,
        description="Enable graph community summary or not.",
    )


class GraphStoreBase(ABC):
    """Graph store base class."""

    def __init__(self, config: GraphStoreConfig):
        """Initialize graph store."""
        self._config = config
        self._conn = None

    @abstractmethod
    def get_config(self) -> GraphStoreConfig:
        """Get the graph store config."""
