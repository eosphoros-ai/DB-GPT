"""Graph store base class."""
import logging
from abc import ABC

from dbgpt._private.pydantic import BaseModel

logger = logging.getLogger(__name__)


class GraphStoreConfig(BaseModel):
    """Graph store config."""


class GraphStoreBase(ABC):
    """Graph store base class."""
