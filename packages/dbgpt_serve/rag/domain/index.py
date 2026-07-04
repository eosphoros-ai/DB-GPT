"""General Domain Knowledge Index - ETL pipeline for local documents."""

import logging
from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.storage.full_text.base import FullTextStoreBase
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase
from dbgpt.storage.vector_store.base import VectorStoreBase
from dbgpt_ext.rag import ChunkParameters
from dbgpt_ext.rag.chunk_manager import ChunkManager

from .base import DomainKnowledgeIndex

logger = logging.getLogger(__name__)


class DomainGeneralIndex(DomainKnowledgeIndex):
    """General domain knowledge index for local documents."""

    async def extract(
        self,
        knowledge: Knowledge,
        chunk_parameter: ChunkParameters,
        extract_image: bool = False,
        **kwargs,
    ) -> List[Chunk]:
        if not knowledge:
            raise ValueError("knowledge must be provided.")
        documents = await knowledge.aload()
        chunk_manager = ChunkManager(
            knowledge=knowledge, chunk_parameter=chunk_parameter
        )
        chunks = chunk_manager.split(documents)
        for chunk in chunks:
            chunk.metadata["chunk_id"] = chunk.chunk_id
        if chunk_parameter.need_index_headers:
            new_chunks = []
            for chunk in chunks:
                for key, value in chunk.metadata.items():
                    if value in chunk_parameter.need_index_headers:
                        new_chunks.append(chunk)
                        break
            return new_chunks
        if extract_image:
            new_chunks = knowledge.extract_images(chunks)
            return new_chunks
        return chunks

    async def transform(
        self,
        chunks: List[Chunk],
        image_extractor=None,
        summary_extractor=None,
        batch_size: int = 1,
        **kwargs,
    ) -> List[Chunk]:
        transform_chunks = chunks
        if image_extractor:
            transform_chunks = await self._process_images(
                chunks, image_extractor, batch_size
            )
        if summary_extractor:
            for chunk in transform_chunks:
                summary_text = await summary_extractor.extract(text=chunk.content)
                chunk.summary = summary_text
        return transform_chunks

    async def _process_images(self, chunks, image_extractor, batch_size=1):
        import asyncio
        processed_chunks = list(chunks)
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            tasks = []
            for chunk in batch:
                if chunk.image_url:
                    tasks.append(
                        self._extract_image_task(chunk, image_extractor)
                    )
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if result is not None and not isinstance(result, Exception):
                        processed_chunks.append(result)
        return processed_chunks

    async def _extract_image_task(self, chunk, image_extractor):
        try:
            image_text = await image_extractor.extract(
                image=chunk.image_url, text=chunk.content
            )
            chunk.content = image_text
            return chunk
        except Exception as e:
            logger.error(f"Error processing image {chunk.image_url}: {e}")
            return None

    async def load(
        self,
        chunks: list[Chunk],
        vector_store: Optional[VectorStoreBase] = None,
        full_text_store: Optional[FullTextStoreBase] = None,
        kg_store: Optional[KnowledgeGraphBase] = None,
        keywords: bool = True,
        max_chunks_once_load: int = 10,
        max_threads: int = 1,
        **kwargs,
    ) -> List[Chunk]:
        if vector_store:
            vector_ids = await vector_store.aload_document_with_limit(
                chunks, max_chunks_once_load, max_threads
            )
            for chunk, vector_id in zip(chunks, vector_ids):
                chunk.vector_id = vector_id
        if full_text_store:
            await full_text_store.aload_document_with_limit(
                chunks, max_chunks_once_load, max_threads
            )
        if kg_store:
            await kg_store.aload_document_with_limit(
                chunks, max_chunks_once_load, max_threads
            )
        return chunks

    async def clean(
        self,
        chunks: list[Chunk],
        node_ids: Optional[list[str]],
        with_keywords: bool = True,
        **kwargs,
    ):
        raise NotImplementedError

    @classmethod
    def domain_type(cls) -> str:
        return "normal"