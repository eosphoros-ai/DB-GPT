"""Tests for citation metadata emitted by the knowledge retrieval tool."""

import json
from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.tools.knowledge_retrieve import (
    make_knowledge_retrieve,
)


class _KnowledgeResource:
    async def retrieve(self, query: str):
        assert query == "revenue"
        return [
            SimpleNamespace(
                chunk_id="chunk-1",
                chunk_name="Revenue section",
                content="Revenue grew by 20 percent.",
                score=0.91,
                metadata={
                    "doc_name": "annual-report.md",
                    "file_path": "reports/annual-report.md",
                    "url": "https://example.test/annual-report",
                },
            )
        ]


@pytest.mark.asyncio
async def test_knowledge_retrieve_preserves_structured_citation_metadata() -> None:
    retrieve = make_knowledge_retrieve({}, [_KnowledgeResource()])

    result = json.loads(await retrieve("revenue"))

    assert result["chunks"] == [
        {
            "output_type": "text",
            "content": "Retrieved 1 relevant documents",
        },
        {
            "output_type": "markdown",
            "content": "[1] Revenue grew by 20 percent.",
        },
    ]
    assert result["citations"] == [
        {
            "id": "chunk-1",
            "sourceName": "annual-report.md",
            "chunkIndex": 1,
            "score": 0.91,
            "path": "reports/annual-report.md",
            "url": "https://example.test/annual-report",
        }
    ]


@pytest.mark.asyncio
async def test_knowledge_retrieve_empty_result_has_no_citations() -> None:
    class _EmptyResource:
        async def retrieve(self, query: str):
            return []

    retrieve = make_knowledge_retrieve({}, [_EmptyResource()])

    result = json.loads(await retrieve("missing"))

    assert result["chunks"][0]["content"] == "No relevant information found"
    assert result.get("citations", []) == []


@pytest.mark.asyncio
async def test_knowledge_retrieve_never_emits_non_standard_json_scores() -> None:
    class _NonFiniteScoreResource:
        async def retrieve(self, query: str):
            return [
                SimpleNamespace(
                    chunk_id="chunk-nan",
                    chunk_name="Metrics",
                    content="A finite excerpt with a non-finite upstream score.",
                    score=float("nan"),
                    metadata={"doc_name": "metrics.md"},
                )
            ]

    retrieve = make_knowledge_retrieve({}, [_NonFiniteScoreResource()])

    raw_result = await retrieve("metrics")
    result = json.loads(raw_result, parse_constant=lambda value: pytest.fail(value))

    assert "NaN" not in raw_result
    assert result["citations"][0]["score"] is None


@pytest.mark.asyncio
async def test_knowledge_retrieve_skips_empty_chunks_without_renumbering() -> None:
    class _SparseResource:
        async def retrieve(self, query: str):
            return [
                SimpleNamespace(
                    chunk_id="chunk-empty",
                    chunk_name="Empty section",
                    content="   ",
                    score=0.8,
                    metadata={"doc_name": "empty.md"},
                ),
                SimpleNamespace(
                    chunk_id="chunk-real",
                    chunk_name="Revenue section",
                    content="Revenue grew by 20 percent.",
                    score=0.91,
                    metadata={"doc_name": "annual-report.md"},
                ),
            ]

    retrieve = make_knowledge_retrieve({}, [_SparseResource()])

    result = json.loads(await retrieve("revenue"))

    assert result["chunks"][1]["content"] == "[2] Revenue grew by 20 percent."
    assert result["citations"] == [
        {
            "id": "chunk-real",
            "sourceName": "annual-report.md",
            "chunkIndex": 2,
            "score": 0.91,
            "path": None,
            "url": None,
        }
    ]
