"""Git Repository Index - ETL pipeline for Git repo knowledge bases."""

import logging
import uuid
from collections import defaultdict
from typing import List

from dbgpt.core import Chunk
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt_ext.rag import ChunkParameters
from dbgpt_ext.rag.chunk_manager import ChunkManager

from .index import DomainGeneralIndex

logger = logging.getLogger(__name__)


class GitRepoIndex(DomainGeneralIndex):
    """Git repository indexing pipeline with document-level summaries."""

    async def extract(
        self,
        knowledge: Knowledge,
        chunk_parameter: ChunkParameters,
        extract_image: bool = False,
        **kwargs,
    ) -> List[Chunk]:
        if not knowledge:
            raise ValueError("knowledge must be provided.")
        # DB-GPT's Knowledge base only has sync _load(); use load() directly.
        # (git_repo_sync_service overrides _load to return pre-built documents)
        documents = knowledge.load()
        if hasattr(knowledge, "extract") and callable(
            getattr(knowledge, "extract", None)
        ):
            try:
                result = knowledge.extract(documents, chunk_parameter)
                if result is not None:
                    all_chunks = []
                    for doc in result:
                        if hasattr(doc, "chunks") and doc.chunks:
                            for chunk in doc.chunks:
                                chunk.metadata["chunk_id"] = chunk.chunk_id
                                all_chunks.append(chunk)
                    if all_chunks:
                        return all_chunks
            except Exception as e:
                logger.warning(f"GitRepoKnowledge.extract() failed, falling back: {e}")
        chunk_manager = ChunkManager(
            knowledge=knowledge, chunk_parameter=chunk_parameter
        )
        chunks = chunk_manager.split(documents)
        for chunk in chunks:
            chunk.metadata["chunk_id"] = chunk.chunk_id
        return chunks

    async def transform(
        self,
        chunks: List[Chunk],
        image_extractor=None,
        summary_extractor=None,
        batch_size: int = 1,
        **kwargs,
    ) -> List[Chunk]:
        transform_chunks = await super().transform(
            chunks,
            image_extractor=image_extractor,
            summary_extractor=None,
            batch_size=batch_size,
            **kwargs,
        )
        for chunk in transform_chunks:
            doc_name = (chunk.metadata or {}).get("doc_name", "")
            file_path = (chunk.metadata or {}).get("file_path", "")
            prefix = ""
            if doc_name:
                prefix += f"[文件: {doc_name}]"
            if file_path:
                prefix += f" [路径: {file_path}]"
            if prefix:
                chunk.content = prefix.strip() + "\n" + chunk.content
        if summary_extractor:
            summary_chunks = await self._generate_doc_summaries(
                transform_chunks, summary_extractor
            )
            transform_chunks.extend(summary_chunks)
        return transform_chunks

    async def _generate_doc_summaries(
        self, chunks: List[Chunk], summary_extractor
    ) -> List[Chunk]:
        doc_chunks = defaultdict(list)
        for chunk in chunks:
            if chunk.chunk_type == "image":
                continue
            doc_id = chunk.metadata.get("doc_id", "") if chunk.metadata else ""
            if doc_id:
                doc_chunks[doc_id].append(chunk)
        summary_chunks = []
        for doc_id, doc_chunk_list in doc_chunks.items():
            try:
                full_text = "\n\n".join(c.content for c in doc_chunk_list if c.content)
                if not full_text.strip():
                    continue
                if len(full_text) > 30000:
                    full_text = full_text[:30000] + "\n...(truncated)"
                first_chunk = doc_chunk_list[0]
                if hasattr(summary_extractor, "generate_summary"):
                    summary_text = await summary_extractor.generate_summary(
                        content=full_text
                    )
                else:
                    summary_text = await summary_extractor.extract(text=full_text)
                    if isinstance(summary_text, list):
                        summary_text = summary_text[0] if summary_text else ""
                if not summary_text:
                    continue
                doc_name = (first_chunk.metadata or {}).get("doc_name", "")
                file_path = (first_chunk.metadata or {}).get("file_path", "")
                sp = ""
                if doc_name:
                    sp += f"[文件: {doc_name}]"
                if file_path:
                    sp += f" [路径: {file_path}]"
                if sp:
                    summary_text = sp.strip() + "\n" + summary_text
                summary_metadata = {
                    **(first_chunk.metadata or {}),
                    "chunk_type": "summary",
                    "doc_id": doc_id,
                }
                summary_chunks.append(
                    Chunk(
                        chunk_id=str(uuid.uuid4()),
                        content=summary_text,
                        metadata=summary_metadata,
                        chunk_type="summary",
                        summary=summary_text,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to generate summary for doc_id={doc_id}: {e}")
        return summary_chunks

    @classmethod
    def domain_type(cls) -> str:
        return "git_repo"
