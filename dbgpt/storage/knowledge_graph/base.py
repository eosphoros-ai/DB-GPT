"""Knowledge graph base class."""
import logging
from abc import ABC

from dbgpt.rag.index.base import IndexStoreBase

logger = logging.getLogger(__name__)


class KnowledgeGraphBase(IndexStoreBase, ABC):
    """Knowledge graph base class."""
