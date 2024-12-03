"""GraphEmbedder class."""

import asyncio
import logging
import re
from typing import Dict, List, Optional

from dbgpt.core import Chunk, LLMClient
from dbgpt.storage.graph_store.graph import Edge, Graph, MemoryGraph, Vertex, GraphElemType
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.rag.transformer.text2vector import Text2Vector

logger = logging.getLogger(__name__)


class GraphEmbedder(Text2Vector):
    """GraphEmbedder class."""

    def __init__(self):
        """Initialize the GraphEmbedder"""
        super().__init__()
    
    async def embed(
        self,
        text: str,
    ) -> List[List[Graph]]:
        """Embed"""
        return await super()._embed(text)
            
    async def batch_embed(
        self,
        graphs_list: List[List[Graph]],
    ) -> List[List[Graph]]:
        """Embed graphs from graphs in batches"""

        for graphs in enumerate(graphs_list):
            for graph in graphs:
                    for vertex in graph.vertices():
                        if vertex.get_prop("vertex_type") == GraphElemType.DOCUMENT.value:
                            text = vertex.get_prop("name")
                        elif vertex.get_prop("vertex_type") == GraphElemType.CHUNK.value:
                            text = vertex.get_prop("content")
                        elif vertex.get_prop("vertex_type") == GraphElemType.ENTITY.value:
                            text = vertex.get_prop("id")
                        else:
                            text = ""
                        vector = self._embed(text)
                        vertex.set_prop("embedding", vector)      

        assert all(x is not None for x in Graph), "All positions should be filled"
        return Graph
    
    def truncate(self):
        """"""

    def drop(self):
        """"""
