"""Semantic search tool for knowledge spaces."""

import logging
import math
import time
from typing import Annotated

from dbgpt.agent.resource.tool.base import tool
from dbgpt.core.interface.report_capture import (
    capture_reference_artifact,
    get_current_artifact_sink,
    sha256_text,
)

from ..chunk_metadata import parse_chunk_metadata

logger = logging.getLogger(__name__)


def _get_rag_service():
    from dbgpt._private.config import Config

    from ..service.service import Service

    system_app = Config().SYSTEM_APP
    if not system_app:
        raise RuntimeError("SYSTEM_APP is not initialized yet")
    return Service.get_instance(system_app)


def _format_chunk_results(chunks, query, knowledge_id):
    lines = [f"Semantic search '{query}' in {knowledge_id}:"]
    chars = len(lines[0])
    for i, chunk in enumerate(chunks):
        content = chunk.content or ""
        score = getattr(chunk, "score", None)
        metadata = parse_chunk_metadata(getattr(chunk, "metadata", None))
        file_path = metadata.get("file_path", "")
        score_str = f" (score: {score:.2f})" if score is not None else ""
        chunk_id = metadata.get("chunk_id") or getattr(chunk, "chunk_id", "")
        entry = (
            "\n---\n### Result "
            f"{i + 1}"
            f"{score_str}"
            " ["
            f"{file_path}"
            "] chunk_id="
            f"{chunk_id}"
            "\n"
            f"{content}"
        )
        chars += len(entry)
        if chars > 8000:
            lines.append(f"\n... {len(chunks) - i} more results.")
            break
        lines.append(entry)
    return "\n".join(lines)


@tool(
    "kb_semantic_search",
    description=(
        "Semantic search in knowledge base. Use only when kb_grep returns "
        "insufficient results."
    ),
)
async def kb_semantic_search(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    query: Annotated[str, "Natural language search query"],
    top_k: Annotated[int, "Number of results"] = 5,
    score_threshold: Annotated[float, "Min score (0-1)"] = 0.0,
) -> str:
    top_k = int(top_k) if top_k else 5
    score_threshold = float(score_threshold) if score_threshold else 0.0
    try:
        service = _get_rag_service()
    except Exception as e:
        return f"Semantic search service unavailable: {e}"
    try:
        from ..api.schemas import KnowledgeRetrieveRequest

        # knowledge_id may be either the numeric space id or the space name.
        # Resolve it to the actual space entity first, then use its numeric id
        # for the retrieve request (KnowledgeRetrieveRequest.space_id is int).
        knowledge_id_str = str(knowledge_id)
        if knowledge_id_str.isdigit():
            space = service.get({"id": int(knowledge_id_str)})
        else:
            space = service.get({"name": knowledge_id_str})
        if space is None:
            return f"Knowledge space {knowledge_id} not found"

        request = KnowledgeRetrieveRequest(
            query=query,
            space_id=space.id,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        capture_enabled = get_current_artifact_sink() is not None
        started = time.perf_counter() if capture_enabled else None
        search_res = await service.retrieve(request, space)
        duration_ms = (
            max(0, int((time.perf_counter() - started) * 1000))
            if started is not None
            else 0
        )
    except Exception as e:
        return f"Semantic search failed: {e}"
    if not search_res:
        return f"No results for '{query}' in {knowledge_id}"
    if capture_enabled:
        for index, chunk in enumerate(search_res):
            metadata = parse_chunk_metadata(chunk.metadata)
            chunk_id = str(metadata.get("chunk_id") or getattr(chunk, "chunk_id", ""))
            document_id = (
                metadata.get("document_id")
                or metadata.get("doc_id")
                or metadata.get("file_id")
            )
            path = metadata.get("file_path") or metadata.get("path")
            source_name = (
                metadata.get("doc_name")
                or metadata.get("document_name")
                or path
                or chunk_id
            )
            raw_score = getattr(chunk, "score", None)
            page = metadata.get("page")
            if page is None:
                page = metadata.get("page_number")
            score = (
                float(raw_score)
                if isinstance(raw_score, (int, float))
                and math.isfinite(float(raw_score))
                and raw_score >= 0
                else None
            )
            capture_reference_artifact(
                reference_type="knowledge",
                source_id=chunk_id,
                action="knowledge.semantic_search",
                duration_ms=duration_ms,
                source_name=source_name,
                uri=f"kb://{space.id}/{document_id or 'unknown'}/{chunk_id}",
                locator={
                    "knowledge_id": str(knowledge_id),
                    "space_id": space.id,
                    "space_name": space.name,
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "chunk_index": metadata.get("chunk_index"),
                    "chunk_db_id": metadata.get("chunk_db_id"),
                    "page": page,
                    "path": path,
                    "start_line": metadata.get("start_line"),
                    "end_line": metadata.get("end_line"),
                },
                excerpt=getattr(chunk, "content", "") or "",
                score=score,
                metadata={
                    "query_sha256": sha256_text(query),
                    "retrieval_query": query[:500],
                    "retrieval_rank": index,
                },
            )
    return _format_chunk_results(search_res, query, knowledge_id)
