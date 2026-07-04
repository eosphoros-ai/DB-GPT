"""Semantic search tool for knowledge spaces."""

import logging
from typing import Annotated

from dbgpt.agent.resource.tool.base import tool

logger = logging.getLogger(__name__)


def _get_rag_service():
    from ..service.service import Service
    from dbgpt._private.config import Config
    system_app = Config().SYSTEM_APP
    if not system_app:
        raise RuntimeError("SYSTEM_APP is not initialized yet")
    return Service.get_instance(system_app)


def _format_chunk_results(chunks, query: str, knowledge_id: str) -> str:
    result_lines = [f"Semantic search '{query}' in knowledge space {knowledge_id}:"]
    MAX_OUTPUT_CHARS = 8000
    current_chars = len(result_lines[0])
    for i, chunk in enumerate(chunks):
        content = chunk.content or ""
        score = getattr(chunk, "score", None)
        metadata = getattr(chunk, "metadata", {}) or {}
        file_path = metadata.get("file_path", "")
        doc_name = metadata.get("doc_name", "")
        score_str = f" (score: {score:.2f})" if score is not None else ""
        source_parts = []
        if file_path:
            source_parts.append(f"file: {file_path}")
        if doc_name and doc_name != file_path:
            source_parts.append(f"doc: {doc_name}")
        source_str = " | " + " | ".join(source_parts) if source_parts else ""
        entry = f"\n---\n### Result {i + 1}{score_str}{source_str}\n{content}"
        current_chars += len(entry)
        if current_chars > MAX_OUTPUT_CHARS:
            result_lines.append(f"\n... {len(chunks) - i} more results not shown.")
            break
        result_lines.append(entry)
    return "\n".join(result_lines)


@tool(
    name="kb_semantic_search",
    description=(
        "Semantic search in knowledge base. "
        "Priority: kb_grep (exact match) > kb_semantic_search (semantic match). "
        "Use this only when kb_grep returns empty or insufficient results."
    ),
)
async def kb_semantic_search(
    knowledge_id: Annotated[str, "Knowledge space ID"],
    query: Annotated[str, "Search query in natural language"],
    top_k: Annotated[int, "Number of results"] = 5,
    score_threshold: Annotated[float, "Minimum score threshold (0-1)"] = 0.0,
) -> str:
    top_k = int(top_k) if top_k else 5
    score_threshold = float(score_threshold) if score_threshold else 0.0
    try:
        service = _get_rag_service()
    except Exception as e:
        logger.error(f"Failed to get RAG service: {e}")
        return f"Semantic search service unavailable: {e}"
    try:
        from ..api.schemas import KnowledgeRetrieveRequest
        request = KnowledgeRetrieveRequest(
            query=query,
            space_id=int(knowledge_id) if knowledge_id.isdigit() else knowledge_id,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        space = service.get({"id": request.space_id})
        if space is None:
            return f"Knowledge space {knowledge_id} not found"
        search_res = await service.retrieve(request, space)
    except Exception as e:
        logger.exception(f"Semantic search failed: {e}")
        return f"Semantic search failed: {e}"
    if not search_res:
        return f"No results found for '{query}' in knowledge space {knowledge_id}"
    return _format_chunk_results(search_res, query, knowledge_id)