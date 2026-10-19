"""Regression tests for DocumentChunkDao space-scoped queries.

The chunk table has no space column — space scoping must go through
document_id IN (...) filters. These tests lock that the chunk DAO's
list/count queries apply the same document_ids (and content) filters so
paged results and total_count stay consistent.
"""

from types import SimpleNamespace

import pytest

from dbgpt.storage.metadata import db

from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


def _add_chunks(dao: DocumentChunkDao, document_id: int, contents):
    documents = [
        SimpleNamespace(
            doc_name=f"doc_{document_id}.txt",
            doc_type="TEXT",
            document_id=document_id,
            content=content,
            meta_info="",
        )
        for content in contents
    ]
    dao.create_documents_chunks(documents)


def test_get_document_chunks_filters_by_document_ids():
    dao = DocumentChunkDao()
    _add_chunks(dao, 1, ["alpha one", "alpha two"])
    _add_chunks(dao, 2, ["beta one"])

    chunks = dao.get_document_chunks(DocumentChunkEntity(), 1, 20, document_ids=[1])

    assert [c.document_id for c in chunks] == [1, 1]


def test_get_document_chunks_count_filters_by_document_ids():
    dao = DocumentChunkDao()
    _add_chunks(dao, 1, ["alpha one", "alpha two"])
    _add_chunks(dao, 2, ["beta one"])

    count = dao.get_document_chunks_count(DocumentChunkEntity(), document_ids=[1])

    assert count == 2


def test_get_document_chunks_count_applies_content_filter():
    dao = DocumentChunkDao()
    _add_chunks(dao, 1, ["alpha one", "gamma two", "alpha three"])
    _add_chunks(dao, 2, ["alpha outsider"])

    listed = dao.get_document_chunks(
        DocumentChunkEntity(content="alpha"), 1, 20, document_ids=[1]
    )
    count = dao.get_document_chunks_count(
        DocumentChunkEntity(content="alpha"), document_ids=[1]
    )

    # items and count must agree: only doc 1's two "alpha" chunks match
    assert len(listed) == 2
    assert count == 2
