"""Define the Community class"""

import logging
from dataclasses import dataclass

from dbgpt.storage.graph_store.graph import Graph

logger = logging.getLogger(__name__)


@dataclass
class Community:
    id: str
    data: Graph = None
    summary: str = None


@dataclass
class CommunityTree:
    """Represents a community tree."""
