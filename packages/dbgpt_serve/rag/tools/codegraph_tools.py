"""Code graph tools for GIT_REPO knowledge spaces."""

import json
import logging
import os
from typing import Annotated
from dbgpt.agent.resource.tool.base import tool
from dbgpt.storage.graph_store.graph import MemoryGraph

logger = logging.getLogger(__name__)
_graph_cache: dict = {}


def _get_graph_cache_dir(knowledge_id):
    return os.path.join(os.path.expanduser("~"), ".dbgpt", "graph_cache", knowledge_id)


def _load_graph(knowledge_id):
    if knowledge_id in _graph_cache:
        return _graph_cache[knowledge_id], None
    graph_file = os.path.join(_get_graph_cache_dir(knowledge_id