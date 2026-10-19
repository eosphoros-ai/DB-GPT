"""Space-scoping tests for the v1 knowledge endpoints.

Locks two security-relevant behaviors:

1. ``/knowledge/{space_name}/chunk/list`` and ``/chunk/edit`` must only
   see/modify chunks belonging to ``space_name`` — the path parameter is
   the authorization boundary, not a decoration.
2. ``/knowledge/{space_name}/query`` must take the space from the URL
   path. The historic route declared ``{vector_name}`` while the handler
   signature expected a ``space_name`` query parameter, silently
   dropping the path value.

``{space_name}``-scoped responses must keep their existing envelope
(``Result.succ``/``Result.failed`` and ``ChunkQueryResponse`` shapes)
so the web UI (which always sends a real space name in the path) keeps
working unchanged.
"""

from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

import dbgpt_app.knowledge.api as knowledge_api
from dbgpt.util import PaginationResult
from dbgpt_app.knowledge.api import (
    chunk_edit,
    chunk_list,
    get_rag_service,
)
from dbgpt_app.knowledge.api import (
    router as knowledge_router,
)
from dbgpt_app.knowledge.request.request import (
    ChunkEditRequest,
    ChunkQueryRequest,
)
from dbgpt_serve.rag.api.schemas import ChunkServeResponse


def _space(name="space_a", space_id=1):
    return SimpleNamespace(id=space_id, name=name)


def _fake_service(
    *,
    space=None,
    documents=(),
    chunk_page=None,
    chunk=None,
    chunk_document=None,
    updated=Mock(),
):
    """Build a fake rag Service covering the methods the endpoints use."""

    def get_document_list(req):
        docs = list(documents)
        if req.get("id") is not None:
            docs = [d for d in docs if d.id == req["id"]]
        return docs

    service = Mock()
    service.get = lambda req: (
        space if (req or {}).get("name") == (space and space.name) else None
    )
    service.get_document_list = get_document_list
    service.get_chunk_list_page = Mock(return_value=chunk_page)
    service.get_chunk_list = lambda req: [chunk] if chunk else []
    service.get_document = lambda req: chunk_document
    service.update_chunk = updated
    return service


class TestChunkListScoping:
    def test_unknown_space_name_is_rejected(self):
        service = _fake_service(space=None)

        result = chunk_list(
            "no_such_space",
            ChunkQueryRequest(page=1, page_size=20),
            service,
        )

        assert result.success is False
        service.get_chunk_list_page.assert_not_called()

    def test_chunks_are_scoped_to_the_space_documents(self):
        documents = [SimpleNamespace(id=11), SimpleNamespace(id=22)]
        chunk_page = PaginationResult(
            items=[ChunkServeResponse(id=1, document_id=11, content="chunk of doc 11")],
            total_count=1,
            total_pages=1,
            page=1,
            page_size=20,
        )
        service = _fake_service(
            space=_space(), documents=documents, chunk_page=chunk_page
        )

        result = chunk_list("space_a", ChunkQueryRequest(page=1, page_size=20), service)

        assert result.success is True
        assert result.data.total == 1
        kwargs = service.get_chunk_list_page.call_args.kwargs
        assert kwargs["document_ids"] == [11, 22]

    def test_document_id_from_another_space_returns_no_chunks(self):
        # space_a contains doc 11 only; a caller asking for doc 99
        # (belonging to another space) must get an empty result, not the
        # other space's chunks.
        documents = [SimpleNamespace(id=11)]
        service = _fake_service(space=_space(), documents=documents)

        result = chunk_list(
            "space_a",
            ChunkQueryRequest(document_id=99, page=1, page_size=20),
            service,
        )

        assert result.success is True
        assert result.data.total == 0
        assert result.data.data == []
        service.get_chunk_list_page.assert_not_called()


class TestChunkEditScoping:
    def test_edit_without_chunk_id_is_rejected_before_lookup(self):
        # edit_request.chunk_id defaults to None; without an explicit
        # guard a {"id": None} DAO query lists the entire chunk table
        # (and the resulting error leaks which space owns it).
        updated = Mock()
        service = _fake_service(
            space=_space(),
            chunk=SimpleNamespace(id=5, document_id=7),
            chunk_document=SimpleNamespace(id=7, space="space_a"),
            updated=updated,
        )
        # mimic DocumentChunkDao.get_list({"id": None}): returns all rows
        service.get_chunk_list = Mock(return_value=[SimpleNamespace(document_id=7)])

        result = chunk_edit("space_a", ChunkEditRequest(content="poisoned"), service)

        assert result.success is False
        service.get_chunk_list.assert_not_called()
        updated.assert_not_called()

    def test_edit_rejects_chunk_of_another_space(self):
        # chunk 5 belongs to document 7 in space_b; editing it via
        # space_a's path must fail and must not touch the chunk.
        updated = Mock()
        service = _fake_service(
            space=_space(),
            chunk=SimpleNamespace(id=5, document_id=7),
            chunk_document=SimpleNamespace(id=7, space="space_b"),
            updated=updated,
        )

        result = chunk_edit(
            "space_a", ChunkEditRequest(chunk_id=5, content="poisoned"), service
        )

        assert result.success is False
        updated.assert_not_called()

    def test_edit_allows_chunk_of_same_space(self):
        updated = Mock()
        service = _fake_service(
            space=_space(),
            chunk=SimpleNamespace(id=5, document_id=7),
            chunk_document=SimpleNamespace(id=7, space="space_a"),
            updated=updated,
        )

        result = chunk_edit(
            "space_a", ChunkEditRequest(chunk_id=5, content="fixed"), service
        )

        assert result.success is True
        updated.assert_called_once()


class TestSimilarityQueryRoute:
    def test_route_path_parameter_is_named_space_name(self):
        paths = [getattr(route, "path", "") for route in knowledge_router.routes]
        assert "/knowledge/{space_name}/query" in paths
        assert not any("{vector_name}" in path for path in paths)

    def _mounted_client(self, fake_service, monkeypatch):
        monkeypatch.setattr(
            knowledge_api.StorageManager,
            "get_instance",
            lambda app: Mock(),
        )
        app = FastAPI()
        # include_router (not raw route appending) so FastAPI wires the
        # dependency_overrides_provider for get_rag_service.
        app.include_router(knowledge_router)
        app.dependency_overrides[get_rag_service] = lambda: fake_service
        return TestClient(app)

    def test_space_comes_from_path_and_must_exist(self, monkeypatch):
        unknown_space = _fake_service(space=None)
        with self._mounted_client(unknown_space, monkeypatch) as client:
            # No ?space_name= query parameter: the route must take the
            # space from the path. Pre-fix this was a 422.
            response = client.post(
                "/knowledge/no_such_space/query",
                json={"query": "hello", "space": "no_such_space", "top_k": 1},
            )
            assert response.status_code == 200
            assert response.json()["success"] is False

    def test_query_retrieves_from_named_space(self, monkeypatch):
        retrieved = SimpleNamespace(
            content="chunk text", metadata={"source": "doc.txt"}
        )
        retriever = Mock()
        retriever.retrieve.return_value = [retrieved]
        monkeypatch.setattr(
            knowledge_api, "EmbeddingRetriever", Mock(return_value=retriever)
        )
        storage_manager = Mock()
        monkeypatch.setattr(
            knowledge_api.StorageManager,
            "get_instance",
            lambda app: storage_manager,
        )

        service = _fake_service(space=_space())
        app = FastAPI()
        app.include_router(knowledge_router)
        app.dependency_overrides[get_rag_service] = lambda: service

        with TestClient(app) as client:
            response = client.post(
                "/knowledge/space_a/query",
                json={"query": "hello", "space": "space_a", "top_k": 3},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["response"][0]["text"] == "chunk text"
            # the vector store must be opened on the *named* space
            kwargs = storage_manager.create_vector_store.call_args.kwargs
            assert kwargs["index_name"] == "space_a"


def test_chunk_edit_happy_path_end_to_end():
    """Prove a legitimate same-space chunk edit succeeds against a real
    database (not a mocked one) — handler → service → DAO."""
    from datetime import datetime
    from types import SimpleNamespace

    from dbgpt.storage.metadata import db
    from dbgpt_serve.rag.models.chunk_db import DocumentChunkDao, DocumentChunkEntity
    from dbgpt_serve.rag.models.document_db import (
        KnowledgeDocumentDao,
        KnowledgeDocumentEntity,
    )
    from dbgpt_serve.rag.models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity
    from dbgpt_serve.rag.service.service import Service

    db.init_db("sqlite:///:memory:")
    db.create_all()
    now = datetime.now()

    space_dao = KnowledgeSpaceDao()
    document_dao = KnowledgeDocumentDao()
    chunk_dao = DocumentChunkDao()

    session = space_dao.get_raw_session()
    session.merge(
        KnowledgeSpaceEntity(
            name="space_a",
            vector_type="Chroma",
            domain_type="Normal",
            gmt_created=now,
            gmt_modified=now,
        )
    )
    session.merge(
        KnowledgeDocumentEntity(
            doc_name="doc.txt",
            doc_type="TEXT",
            space="space_a",
            chunk_size=1,
            status="FINISHED",
            content="original document",
            gmt_created=now,
            gmt_modified=now,
        )
    )
    session.commit()
    session.close()

    document = document_dao.get_list({"space": "space_a"})[0]
    chunk_dao.create_documents_chunks(
        [
            SimpleNamespace(
                doc_name="doc.txt",
                doc_type="TEXT",
                document_id=document.id,
                content="original chunk",
                meta_info="",
            )
        ]
    )
    chunk = chunk_dao.get_document_chunks(
        DocumentChunkEntity(document_id=document.id), 1, 20
    )[0]

    service = Service(
        system_app=Mock(),
        config=Mock(),
        dao=space_dao,
        document_dao=document_dao,
        chunk_dao=chunk_dao,
    )

    result = chunk_edit(
        "space_a", ChunkEditRequest(chunk_id=chunk.id, content="updated"), service
    )

    assert result.success is True, result.err_msg
    refreshed = chunk_dao.get_document_chunks(DocumentChunkEntity(id=chunk.id), 1, 20)[
        0
    ]
    assert refreshed.content == "updated"
