"""Full Text Operator."""

import os
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.util.i18n_utils import _


class FullTextStorageOperator(MapOperator[List[Chunk], List[Chunk]]):
    """Full Text Operator."""

    metadata = ViewMetadata(
        label=_("Full Text Storage Operator"),
        name="full text_storage_operator",
        description=_("Persist embeddings into full text storage."),
        category=OperatorCategory.RAG,
        parameters=[
            Parameter.build_from(
                _("Full Text Connector"),
                "full_text_store",
                FullTextStoreBase,
                description=_("The full text store."),
                alias=["full_text_store"],
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
                    "The assembled chunks, it has been persisted to full text store."
                ),
                is_list=True,
            )
        ],
    )

    def __init__(
        self,
        full_text_store: Optional[FullTextStoreBase] = None,
        max_chunks_once_load: Optional[int] = None,
        **kwargs,
    ):
        """Init the datasource operator."""
        MapOperator.__init__(self, **kwargs)
        self._full_text_store = full_text_store
        self._embeddings = full_text_store.get_config().embedding_fn
        self._max_chunks_once_load = max_chunks_once_load
        self.full_text_store = full_text_store

    async def map(self, chunks: List[Chunk]) -> List[Chunk]:
        """Persist chunks in full text db."""
        max_chunks_once_load = self._max_chunks_once_load or int(
            os.getenv("KNOWLEDGE_MAX_CHUNKS_ONCE_LOAD", 10)
        )
        full_text_ids = await self._full_text_store.aload_document_with_limit(
            chunks, max_chunks_once_load
        )
        for chunk, full_text_id in zip(chunks, full_text_ids):
            chunk.chunk_id = str(full_text_id)
        return chunks
