"""knowledge_retrieve tool — search the knowledge base."""

import json
import math
import time
from typing import Any, Dict, List

from dbgpt.agent.resource.tool.base import tool
from dbgpt.core.interface.report_capture import (
    capture_reference_artifact,
    get_current_artifact_sink,
    sha256_text,
)
from dbgpt_serve.rag.chunk_metadata import parse_chunk_metadata


def make_knowledge_retrieve(react_state: Dict[str, Any], knowledge_resources: List):
    @tool(
        description=(
            "Retrieve relevant information from the knowledge base. "
            "Use this tool when the user question involves content that may be "
            'in the knowledge base. Parameters: {{"query": "search query"}}'
        )
    )
    async def knowledge_retrieve(query: str) -> str:
        if not knowledge_resources:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": "No knowledge base available",
                        }
                    ],
                    "citations": [],
                },
                ensure_ascii=False,
            )

        resource = knowledge_resources[0]
        try:
            capture_enabled = get_current_artifact_sink() is not None
            started = time.perf_counter() if capture_enabled else None
            chunks = await resource.retrieve(query)
            duration_ms = (
                max(0, int((time.perf_counter() - started) * 1000))
                if started is not None
                else 0
            )
            if chunks:
                # Cap per-chunk and total size so a few large chunks can't
                # overflow the LLM context window. Larger outputs are
                # persisted to disk by the ToolResultStorage layer.
                MAX_CHUNK_CHARS = 4000
                MAX_TOTAL_CHARS = 20_000
                content_parts = []
                citations = []
                total_chars = 0
                for i, chunk in enumerate(chunks[:5]):
                    chunk_content = (chunk.content or "")[:MAX_CHUNK_CHARS]
                    if not chunk_content.strip():
                        continue
                    if total_chars + len(chunk_content) > MAX_TOTAL_CHARS:
                        content_parts.append(
                            f"[{i + 1}] ... [truncated: total output cap "
                            f"{MAX_TOTAL_CHARS} chars reached]"
                        )
                        break
                    content_parts.append(f"[{i + 1}] {chunk_content}")
                    total_chars += len(chunk_content)
                    metadata = parse_chunk_metadata(chunk.metadata)
                    path = metadata.get("file_path") or metadata.get("path")
                    source_name = (
                        metadata.get("doc_name")
                        or metadata.get("document_name")
                        or metadata.get("doc")
                        or metadata.get("source")
                        or path
                        or getattr(chunk, "chunk_name", None)
                        or "Knowledge Base"
                    )
                    url = metadata.get("url") or metadata.get("source_url")
                    score = getattr(chunk, "score", None)
                    finite_score = (
                        float(score)
                        if isinstance(score, (int, float))
                        and math.isfinite(float(score))
                        else None
                    )
                    citations.append(
                        {
                            "id": str(
                                getattr(chunk, "chunk_id", None)
                                or metadata.get("chunk_id")
                                or f"knowledge-{i + 1}"
                            ),
                            "sourceName": str(source_name),
                            "chunkIndex": metadata.get("chunk_index"),
                            "excerpt": chunk_content,
                            "score": finite_score,
                            "path": str(path) if path else None,
                            "url": str(url) if url else None,
                        }
                    )
                    if capture_enabled:
                        chunk_id = str(
                            getattr(chunk, "chunk_id", None)
                            or metadata.get("chunk_id")
                            or f"knowledge-{i + 1}"
                        )
                        document_id = (
                            metadata.get("document_id")
                            or metadata.get("doc_id")
                            or metadata.get("file_id")
                        )
                        page = metadata.get("page")
                        if page is None:
                            page = metadata.get("page_number")
                        knowledge_id = metadata.get("space_id") or metadata.get(
                            "knowledge_id"
                        )
                        if knowledge_id is None:
                            try:
                                knowledge_id = getattr(
                                    resource, "name", None
                                ) or getattr(resource, "value", None)
                            except Exception:
                                knowledge_id = None
                        kb_uri = (
                            f"kb://{knowledge_id or 'unknown'}/"
                            f"{document_id or 'unknown'}/{chunk_id}"
                        )
                        capture_reference_artifact(
                            reference_type="knowledge",
                            source_id=chunk_id,
                            action="knowledge_retrieve",
                            duration_ms=duration_ms,
                            source_name=source_name,
                            uri=str(url) if url else kb_uri,
                            locator={
                                "knowledge_id": knowledge_id,
                                "space_name": metadata.get("space_name")
                                or getattr(resource, "name", None),
                                "document_id": document_id,
                                "chunk_id": chunk_id,
                                "chunk_index": metadata.get("chunk_index"),
                                "chunk_db_id": metadata.get("chunk_db_id"),
                                "page": page,
                                "path": (str(path) if path else None),
                                "start_line": metadata.get("start_line"),
                                "end_line": metadata.get("end_line"),
                            },
                            excerpt=chunk.content or "",
                            score=finite_score,
                            metadata={
                                "query_sha256": sha256_text(query),
                                "retrieval_query": query[:500],
                                "retrieval_rank": i,
                            },
                        )
                content = "\n".join(content_parts)
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": (
                                    f"Retrieved {len(chunks)} relevant documents"
                                ),
                            },
                            {"output_type": "markdown", "content": content},
                        ],
                        "citations": citations,
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                )
            else:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": "No relevant information found",
                            }
                        ],
                        "citations": [],
                    },
                    ensure_ascii=False,
                )
        except Exception as e:
            return json.dumps(
                {
                    "chunks": [
                        {
                            "output_type": "text",
                            "content": f"Knowledge retrieval failed: {str(e)}",
                        }
                    ],
                    "citations": [],
                },
                ensure_ascii=False,
            )

    return knowledge_retrieve
