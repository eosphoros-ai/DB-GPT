"""Partial indexing must not bind a failed chunk to a successful neighbor ID."""

import json
from types import SimpleNamespace

import pytest

from dbgpt.core import Chunk
from dbgpt.storage.base import IndexStoreBase
from dbgpt.storage.metadata import DatabaseManager
from dbgpt_serve.rag.chunk_metadata import prepare_document_chunks
from dbgpt_serve.rag.domain.index import DomainGeneralIndex
from dbgpt_serve.rag.models.chunk_db import DocumentChunkDao, DocumentChunkEntity
from dbgpt_serve.rag.tools import kb_file_tools


def chunks_and_document():
    chunks = [
        Chunk(chunk_id=key, content=content)
        for key, content in [
            ("A", "SUCCESS_A_ONLY"),
            ("B", "FAILED_B_ONLY"),
            ("C", "SUCCESS_C_ONLY"),
        ]
    ]
    return chunks, SimpleNamespace(id=7, doc_name="source.txt", summary="{}")


@pytest.mark.parametrize("ids", [["A", "C"], ["C", "A"], ["new-A", "new-C"], []])
def test_partial_success_ids_never_shift_source_identity(ids):
    chunks, doc = chunks_and_document()
    prepare_document_chunks(chunks, doc)
    prepare_document_chunks(chunks, doc, ids)
    assert [c.metadata["chunk_id"] for c in chunks] == ["A", "B", "C"]
    assert [c.metadata["chunk_index"] for c in chunks] == [0, 1, 2]


def test_complete_reordered_existing_ids_are_matched_by_identity():
    chunks, doc = chunks_and_document()
    prepare_document_chunks(chunks, doc, ["C", "A", "B"])
    assert [c.metadata["chunk_id"] for c in chunks] == ["A", "B", "C"]


def test_complete_ordered_replacement_ids_keep_existing_store_contract():
    chunks, doc = chunks_and_document()
    prepare_document_chunks(chunks, doc, ["vector-A", "vector-B", "vector-C"])
    assert [c.metadata["chunk_id"] for c in chunks] == [
        "vector-A",
        "vector-B",
        "vector-C",
    ]


class PartialIndex:
    """Deterministic failing backend using the real per-chunk fallback code."""

    _max_chunks_once_load = 10
    _max_threads = 1
    _safe_aload_group = IndexStoreBase._safe_aload_group
    _run_tasks_with_concurrency = IndexStoreBase._run_tasks_with_concurrency
    aload_document_with_limit = IndexStoreBase.aload_document_with_limit

    def __init__(self):
        self.stored = {}

    async def aload_document(self, chunks, file_id=None):
        if any(c.chunk_id == "B" for c in chunks):
            raise ValueError("Embedding failed for B")
        for chunk in chunks:
            self.stored[chunk.chunk_id] = chunk.content
        return [c.chunk_id for c in chunks]


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_duplicate", [False, True])
async def test_partial_index_and_sqlite_kb_cat_return_only_requested_source(
    tmp_path, monkeypatch, legacy_duplicate
):
    chunks, doc = chunks_and_document()
    prepare_document_chunks(chunks, doc)
    backend = PartialIndex()
    ids = await backend.aload_document_with_limit(chunks)
    assert ids == ["A", "C"]
    assert backend.stored["C"] == "SUCCESS_C_ONLY"
    prepare_document_chunks(chunks, doc, ids)
    if legacy_duplicate:
        # A row already persisted by the old implementation cannot be repaired
        # by guessing which of the duplicate C identities was the original.
        chunks[1].metadata["chunk_id"] = "C"
    manager = DatabaseManager()
    manager.init_db("sqlite:///" + (tmp_path / "chunks.db").as_posix())
    DocumentChunkEntity.metadata.create_all(
        manager.engine, tables=[DocumentChunkEntity.__table__]
    )
    dao = DocumentChunkDao(manager)
    dao.create_documents_chunks(
        [
            SimpleNamespace(
                doc_name=doc.doc_name,
                doc_type="TXT",
                document_id=doc.id,
                content=c.content,
                meta_info=json.dumps(c.metadata),
            )
            for c in chunks
        ]
    )
    file_info = {
        "doc_id": doc.id,
        "doc_name": doc.doc_name,
        "file_path": doc.doc_name,
        "vector_ids": ids,
    }
    monkeypatch.setattr(
        kb_file_tools, "_find_doc_by_file_path", lambda *args: file_info
    )
    monkeypatch.setattr(
        kb_file_tools, "_get_chunk_dao", lambda: (dao, DocumentChunkEntity)
    )
    try:
        content = await kb_file_tools.kb_cat("space", "source.txt", chunk_id="C")
        if legacy_duplicate:
            assert "ambiguous source identities" in content
            assert "SUCCESS_C_ONLY" not in content
        else:
            assert "SUCCESS_C_ONLY" in content
        assert "FAILED_B_ONLY" not in content
    finally:
        manager.engine.dispose()


@pytest.mark.asyncio
async def test_domain_index_does_not_attach_neighbor_vector_id():
    chunks, doc = chunks_and_document()
    await DomainGeneralIndex().load(chunks, vector_store=PartialIndex())
    assert chunks[0].metadata.get("vector_id") == "A"
    assert chunks[1].metadata.get("vector_id") is None
    assert chunks[2].metadata.get("vector_id") == "C"
