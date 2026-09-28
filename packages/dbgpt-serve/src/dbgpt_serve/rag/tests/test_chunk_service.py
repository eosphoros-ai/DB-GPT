"""Tests for Service.get_chunk_list_page space-scoped behavior.

get_chunk_list_page must support a document_ids bound so callers can
scope chunk listing to one knowledge space (the chunk table has no
space column; spaces are represented by their document id sets).
"""

from datetime import datetime
from unittest.mock import Mock

import pytest

from dbgpt.util import PaginationResult

from ..models.chunk_db import DocumentChunkDao, DocumentChunkEntity
from ..service.service import Service


@pytest.fixture
def chunk_dao():
    return Mock(spec=DocumentChunkDao)


@pytest.fixture
def service(chunk_dao):
    return Service(
        system_app=Mock(),
        config=Mock(),
        dao=Mock(),
        document_dao=Mock(),
        chunk_dao=chunk_dao,
    )


def _entity(chunk_id: int, document_id: int) -> DocumentChunkEntity:
    return DocumentChunkEntity(
        id=chunk_id,
        document_id=document_id,
        doc_name=f"doc_{document_id}.txt",
        doc_type="TEXT",
        content=f"content {chunk_id}",
        gmt_created=datetime(2026, 1, 1, 0, 0, 0),
        gmt_modified=datetime(2026, 1, 1, 0, 0, 0),
    )


def test_get_chunk_list_page_without_document_ids_delegates(chunk_dao, service):
    chunk_dao.get_list_page.return_value = PaginationResult(
        items=[], total_count=0, total_pages=0, page=1, page_size=20
    )

    result = service.get_chunk_list_page({"content": None}, 1, 20, document_ids=None)

    chunk_dao.get_list_page.assert_called_once_with({"content": None}, 1, 20)
    assert result.total_count == 0


def test_get_chunk_list_page_empty_document_ids_returns_empty_page(chunk_dao, service):
    result = service.get_chunk_list_page({"content": None}, 1, 20, document_ids=[])

    assert result.items == []
    assert result.total_count == 0
    assert result.page == 1
    assert result.page_size == 20
    chunk_dao.get_list_page.assert_not_called()
    chunk_dao.get_document_chunks.assert_not_called()


def test_get_chunk_list_page_with_document_ids_uses_filtered_path(chunk_dao, service):
    entities = [_entity(10, 1), _entity(11, 1)]
    request_entity = DocumentChunkEntity()
    chunk_dao.from_request.return_value = request_entity
    chunk_dao.get_document_chunks.return_value = entities
    chunk_dao.get_document_chunks_count.return_value = 2
    chunk_dao.to_response.side_effect = lambda e: e  # passthrough, assert on entities

    result = service.get_chunk_list_page({"content": None}, 1, 20, document_ids=[1])

    assert result.items == entities
    assert result.total_count == 2
    assert result.total_pages == 1
    assert result.page == 1
    assert result.page_size == 20
    args, kwargs = chunk_dao.get_document_chunks.call_args
    # positional: (entity, page, page_size), keyword or positional: document_ids
    assert (args[1], args[2]) == (1, 20)
    doc_ids = kwargs.get("document_ids") or (args[3] if len(args) > 3 else None)
    assert doc_ids == [1]
    chunk_dao.get_document_chunks_count.assert_called_once_with(
        request_entity, document_ids=[1]
    )
