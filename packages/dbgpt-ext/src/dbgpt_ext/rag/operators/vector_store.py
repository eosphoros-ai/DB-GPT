"""Vector Storage Operator."""

import os
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt.util.i18n_utils import _


class VectorStorageOperator(MapOperator[List[Chunk], List[Chunk]]):
    """Vector Storage Operator."""

    metadata = ViewMetadata(
        label=_("Vector Storage Operator"),
        name="vector_storage_operator",
        description=_("Persist embeddings into vector storage."),
        category=OperatorCategory.RAG,
        parameters=[
            Parameter.build_from(
                _("Vector Store Connector"),
                "vector_store",
                VectorStoreBase,
                description=_("The vector store."),
                alias=["vector_store"],
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
                    "The assembled chunks, it has been persisted to vector store."
                ),
                is_list=True,
            )
        ],
    )

    def __init__(
        self,
        vector_store: Optional[VectorStoreBase] = None,
        max_chunks_once_load: Optional[int] = None,
        **kwargs,
    ):
        """Init the datasource operator."""
        MapOperator.__init__(self, **kwargs)
        self._vector_store = vector_store
        self._embeddings = vector_store.embeddings
        self._max_chunks_once_load = max_chunks_once_load
        self.vector_store = vector_store

    async def map(self, chunks: List[Chunk]) -> List[Chunk]:
        """Persist chunks in vector db."""
        max_chunks_once_load = self._max_chunks_once_load or int(
            os.getenv("KNOWLEDGE_MAX_CHUNKS_ONCE_LOAD", 10)
        )
        vector_ids = await self._vector_store.aload_document_with_limit(
            chunks, max_chunks_once_load
        )
        for chunk, vector_id in zip(chunks, vector_ids):
            chunk.chunk_id = str(vector_id)
        return chunks
