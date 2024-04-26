"""Graph store base class."""
import logging
from abc import ABC
from typing import Any,List,Optional,Dict
from dbgpt._private.pydantic import BaseModel

logger = logging.getLogger(__name__)


class GraphStoreConfig(BaseModel):
    """Graph store config."""


class GraphStoreBase(ABC):
    """Graph store base class."""
    @property
    def client(self) -> Any:
        """Get client."""

    def get_triplets(self, subj: str) -> List[List[str]]:
        """Get triplets."""

    def insert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        ...

    def delete_triplets(self, subj: str, rel: str, obj: str) -> None:
        """Delete triplet."""
        ...

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the graph store."""
        ...

    def query(self, query: str, param_map: Optional[Dict[str, Any]] = {}) -> Any:
        """Query the graph store with statement and parameters."""
        ...