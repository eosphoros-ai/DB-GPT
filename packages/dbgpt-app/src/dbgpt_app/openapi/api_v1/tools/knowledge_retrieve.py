"""knowledge_retrieve tool — search the knowledge base."""

import json
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
                    ]
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
                total_chars = 0
                for i, chunk in enumerate(chunks[:5]):
                    chunk_content = (chunk.content or "")[:MAX_CHUNK_CHARS]
                    if total_chars + len(chunk_content) > MAX_TOTAL_CHARS:
                        content_parts.append(
                            f"[{i + 1}] ... [truncated: total output cap "
                            f"{MAX_TOTAL_CHARS} chars reached]"
                        )
                        break
                    content_parts.append(f"[{i + 1}] {chunk_content}")
                    total_chars += len(chunk_content)
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
                        ]
                    },
                    ensure_ascii=False,
                )
            else:
                return json.dumps(
                    {
                        "chunks": [
                            {
                                "output_type": "text",
                                "content": "No relevant information found",
                            }
                        ]
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
                    ]
                },
                ensure_ascii=False,
            )

    return knowledge_retrieve
