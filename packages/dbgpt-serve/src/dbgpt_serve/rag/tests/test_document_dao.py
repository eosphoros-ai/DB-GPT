"""Regression tests for KnowledgeDocumentDao.update_knowledge_document.

A background document sync holds a detached KnowledgeDocumentEntity and
writes it back via session.merge() when it finishes. merge() re-inserts the
row when it no longer exists, so a document deleted while the sync was in
flight used to come back as FINISHED. update_knowledge_document must skip
the write-back instead of resurrecting the deleted row.
"""

import pytest

from dbgpt.storage.metadata import db

from ..models.document_db import KnowledgeDocumentDao, KnowledgeDocumentEntity


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db("sqlite:///:memory:")
    db.create_all()
    yield


def _document(**kwargs) -> KnowledgeDocumentEntity:
    values = {
        "doc_name": "sample.txt",
        "doc_type": "TEXT",
        "space": "space_a",
        "status": "RUNNING",
        "content": "body",
        "result": "",
        "summary": "",
    }
    values.update(kwargs)
    return KnowledgeDocumentEntity(**values)


def test_update_knowledge_document_updates_existing_row():
    dao = KnowledgeDocumentDao()
    doc_id = dao.create_knowledge_document(_document())

    doc = dao.document_by_id(doc_id)
    doc.status = "FINISHED"
    updated_id = dao.update_knowledge_document(doc)

    assert updated_id == doc_id
    assert dao.document_by_id(doc_id).status == "FINISHED"


def test_update_knowledge_document_does_not_resurrect_deleted_row():
    dao = KnowledgeDocumentDao()
    doc_id = dao.create_knowledge_document(_document())

    # The background task keeps a detached snapshot of the document.
    in_flight_doc = dao.document_by_id(doc_id)

    # The user deletes the document while the sync is still running.
    dao.raw_delete(KnowledgeDocumentEntity(id=doc_id))

    in_flight_doc.status = "FINISHED"
    updated_id = dao.update_knowledge_document(in_flight_doc)

    assert updated_id is None
    assert dao.document_by_id(doc_id) is None
