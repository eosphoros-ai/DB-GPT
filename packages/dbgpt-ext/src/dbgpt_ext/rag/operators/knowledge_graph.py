"""Knowledge Graph Operator."""

import os
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase
from dbgpt.util.i18n_utils import _


class KnowledgeGraphOperator(MapOperator[List[Chunk], List[Chunk]]):
    """Knowledge Graph Operator."""

    metadata = ViewMetadata(
        label=_("Knowledge Graph Operator"),
        name="knowledge_graph_operator",
        description=_("Extract Documents and persist into graph database."),
        category=OperatorCategory.RAG,
        parameters=[
            Parameter.build_from(
                _("Knowledge Graph Connector"),
                "graph_store",
                KnowledgeGraphBase,
                description=_("The knowledge graph."),
                alias=["graph_store"],
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Chunks"),
                "chunks",
                List[Chunk],
                description=_("The text split chunks by chunk manager."),
                is_list=True,
            )
        ],
        outputs=[
            IOField.build_from(
                _("Chunks"),
                "chunks",
                List[Chunk],
                description=_(
                    "The assembled chunks, it has been persisted to graph store."
                ),
                is_list=True,
            )
        ],
    )

    def __init__(
        self,
        graph_store: Optional[KnowledgeGraphBase] = None,
        max_chunks_once_load: Optional[int] = None,
        **kwargs,
    ):
        """Init the Knowledge Graph operator."""
        MapOperator.__init__(self, **kwargs)
        self._graph_store = graph_store
        self._embeddings = graph_store.embeddings
        self._max_chunks_once_load = max_chunks_once_load
        self.graph_store = graph_store

    async def map(self, chunks: List[Chunk]) -> List[Chunk]:
        """Persist chunks in graph db."""
        max_chunks_once_load = self._max_chunks_once_load or int(
            os.getenv("KNOWLEDGE_MAX_CHUNKS_ONCE_LOAD", 10)
        )
        graph_ids = await self._graph_store.aload_document_with_limit(
            chunks, max_chunks_once_load
        )
        for chunk, graph_id in zip(chunks, graph_ids):
            chunk.chunk_id = str(graph_id)
        return chunks
