"""Semantic search tool for knowledge spaces."""

import logging
from typing import Annotated

from dbgpt.agent.resource.tool.base import tool

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
        metadata = getattr(chunk, "metadata", {}) or {}
        file_path = metadata.get("file_path", "")
        score_str = f" (score: {score:.2f})" if score is not None else ""
        entry = f"\n---\n### Result {i + 1}{score_str} [{file_path}]\n{content}"
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
        search_res = await service.retrieve(request, space)
    except Exception as e:
        return f"Semantic search failed: {e}"
    if not search_res:
        return f"No results for '{query}' in {knowledge_id}"
    return _format_chunk_results(search_res, query, knowledge_id)
