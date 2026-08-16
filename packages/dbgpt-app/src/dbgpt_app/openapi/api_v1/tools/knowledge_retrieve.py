"""knowledge_retrieve tool — search the knowledge base."""

import json
import math
from typing import Any, Dict, List

from dbgpt.agent.resource.tool.base import tool


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
            chunks = await resource.retrieve(query)
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
                    metadata = (
                        chunk.metadata if isinstance(chunk.metadata, dict) else {}
                    )
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
                            "chunkIndex": i + 1,
                            "score": finite_score,
                            "path": str(path) if path else None,
                            "url": str(url) if url else None,
                        }
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
