"""Knowledge-space creation must not persist an unusable graph configuration."""

import socket

import pytest

from dbgpt._private.config import Config
from dbgpt.component import SystemApp
from dbgpt.storage.metadata import db
from dbgpt_app.config import ApplicationConfig
from dbgpt_app.knowledge.request.request import KnowledgeSpaceRequest
from dbgpt_app.knowledge.service import KnowledgeService
from dbgpt_ext.storage.graph_store.tugraph_store import TuGraphStoreConfig
from dbgpt_serve.rag.models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity


@pytest.fixture
def graph_space_context(tmp_path, monkeypatch):
    """Use the real service, configuration, and SQLite metadata DAO."""
    system_app = SystemApp()
    app_config = ApplicationConfig()
    system_app.config.configs["app_config"] = app_config
    monkeypatch.setattr(Config(), "SYSTEM_APP", system_app)
    db.init_db(f"sqlite:///{tmp_path / 'knowledge.sqlite'}")
    db.create_all()
    return KnowledgeService(), KnowledgeSpaceDao(), app_config


@pytest.mark.parametrize("name", ["123456", "00123", "space_alpha", "alpha123"])
def test_unconfigured_graph_space_is_not_persisted(graph_space_context, name):
    service, dao, _ = graph_space_context
    request = KnowledgeSpaceRequest(name=name, vector_type="KnowledgeGraph")

    with pytest.raises(ValueError, match="Graph storage is not configured"):
        service.create_knowledge_space(request)

    assert dao.get_knowledge_space(KnowledgeSpaceEntity(name=name)) == []


@pytest.mark.parametrize("name", ["123456", "00123", "space_alpha", "alpha123"])
def test_configured_graph_space_creation_does_not_connect(
    graph_space_context, monkeypatch, name
):
    service, dao, app_config = graph_space_context
    app_config.rag.storage.graph = TuGraphStoreConfig()
    connection_attempts = []

    def reject_connect(_socket, address):
        connection_attempts.append(address)
        raise AssertionError("Creating metadata must not connect to TuGraph")

    monkeypatch.setattr(socket.socket, "connect", reject_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_connect)
    space_id = service.create_knowledge_space(
        KnowledgeSpaceRequest(name=name, vector_type="KnowledgeGraph")
    )

    spaces = dao.get_knowledge_space(KnowledgeSpaceEntity(name=name))
    assert len(spaces) == 1
    assert spaces[0].id == space_id
    assert spaces[0].vector_type == "KnowledgeGraph"
    assert connection_attempts == []


@pytest.mark.parametrize("storage_type", ["VectorStore", "Chroma"])
def test_vector_space_creation_without_graph_config(graph_space_context, storage_type):
    service, dao, app_config = graph_space_context
    assert app_config.rag.storage.graph is None

    space_id = service.create_knowledge_space(
        KnowledgeSpaceRequest(name="vector_space", vector_type=storage_type)
    )

    spaces = dao.get_knowledge_space(KnowledgeSpaceEntity(name="vector_space"))
    assert len(spaces) == 1
    assert spaces[0].id == space_id
    expected_type = (
        app_config.rag.storage.vector.get_type_value()
        if storage_type == "VectorStore"
        else storage_type
    )
    assert spaces[0].vector_type == expected_type


def test_invalid_graph_space_name_keeps_existing_error(graph_space_context):
    service, dao, _ = graph_space_context

    with pytest.raises(Exception, match="space name:invalid-name invalid"):
        service.create_knowledge_space(
            KnowledgeSpaceRequest(name="invalid-name", vector_type="KnowledgeGraph")
        )

    assert dao.get_knowledge_space(KnowledgeSpaceEntity()) == []


def test_existing_graph_space_keeps_duplicate_error(graph_space_context):
    service, dao, app_config = graph_space_context
    app_config.rag.storage.graph = TuGraphStoreConfig()
    request = KnowledgeSpaceRequest(name="existing_space", vector_type="KnowledgeGraph")
    service.create_knowledge_space(request)
    app_config.rag.storage.graph = None

    with pytest.raises(Exception, match="space name:existing_space have already named"):
        service.create_knowledge_space(request)

    assert (
        len(dao.get_knowledge_space(KnowledgeSpaceEntity(name="existing_space"))) == 1
    )
