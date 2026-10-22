"""Knowledge-space display identity must remain separate from the source file."""

import importlib
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_capture_keeps_space_name_and_document_identity(monkeypatch):
    module = importlib.import_module(
        "dbgpt_app.openapi.api_v1.tools.knowledge_retrieve"
    )
    captured = []
    monkeypatch.setattr(module, "get_current_artifact_sink", lambda: object())
    monkeypatch.setattr(
        module, "capture_reference_artifact", lambda **values: captured.append(values)
    )

    class Resource:
        name = "Olist_Analytics_Governance"

        async def retrieve(self, query):
            return [
                SimpleNamespace(
                    chunk_id="chunk-1",
                    content="Original governing rule",
                    score=0.9,
                    metadata={
                        "space_id": 1,
                        "document_id": 7,
                        "doc_name": "metrics.md",
                        "chunk_index": 2,
                        "start_line": 10,
                    },
                )
            ]

    await module.make_knowledge_retrieve({}, [Resource()])("governing rules")
    assert len(captured) == 1
    evidence = captured[0]
    assert evidence["source_name"] == "metrics.md"
    assert evidence["locator"]["space_name"] == "Olist_Analytics_Governance"
    assert evidence["locator"]["document_id"] == 7
    assert evidence["locator"]["chunk_id"] == "chunk-1"
    assert evidence["locator"]["start_line"] == 10
    assert evidence["excerpt"] == "Original governing rule"
