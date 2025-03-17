from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from dbgpt.component import SystemApp
from dbgpt_serve.core.tests.conftest import (  # noqa: F401
    asystem_app,
    client,
    config,
    system_app,
)

from ..api.schemas import (
    DocumentServeRequest,
    DocumentServeResponse,
    SpaceServeResponse,
)
from ..models.chunk_db import DocumentChunkDao
from ..models.document_db import KnowledgeDocumentDao
from ..models.models import KnowledgeSpaceDao, SpaceServeRequest
from ..service.service import Service


@pytest.fixture
def mock_system_app():
    return Mock()


@pytest.fixture
def mock_dao():
    return AsyncMock(KnowledgeSpaceDao)


@pytest.fixture
def mock_document_dao():
    return AsyncMock(KnowledgeDocumentDao)


@pytest.fixture
def mock_chunk_dao():
    return AsyncMock(DocumentChunkDao)


@pytest.fixture
def service(system_app: SystemApp, mock_dao, mock_document_dao, mock_chunk_dao, config):
    return Service(
        system_app=system_app,
        config=config,
        dao=mock_dao,
        document_dao=mock_document_dao,
        chunk_dao=mock_chunk_dao,
    )


@pytest.mark.asyncio
async def test_create_space(service):
    request = SpaceServeRequest(name="Test2Space")

    service.get = Mock(return_value=None)
    service._dao.create_knowledge_space = Mock(
        return_value={"id": "1", "name": "TestSpace"}
    )

    response = service.create_space(request)

    assert response["name"] == "TestSpace"
    service._dao.create_knowledge_space.assert_called_once_with(request)


def test_create_space_already_exists(service):
    request = SpaceServeRequest(name="ExistingSpace")
    existing_space = {"id": "1", "name": "ExistingSpace"}

    service.get = Mock(return_value=existing_space)  # Simulate existing space

    with pytest.raises(HTTPException) as excinfo:
        service.create_space(request)

    assert excinfo.value.status_code == 400
    assert "have already named" in excinfo.value.detail


def test_update_space(service):
    request = SpaceServeRequest(id="1", name="UpdatedSpace")
    existing_space = [SpaceServeRequest(name="ExistingSpace")]

    service._dao.get_knowledge_space = Mock(return_value=existing_space)
    service._dao.update_knowledge_space = Mock(return_value=request)

    response = service.update_space(request)

    assert response.name == "UpdatedSpace"
    service._dao.update_knowledge_space.assert_called_once()


def test_update_space_not_found(service):
    request = SpaceServeRequest(id="1", name="NonExistentSpace")
    service._dao.get_knowledge_space = Mock(return_value=[])

    with pytest.raises(HTTPException) as excinfo:
        service.update_space(request)

    assert excinfo.value.status_code == 400
    assert "no space name named" in excinfo.value.detail


@pytest.mark.asyncio
async def test_create_document(service):
    request = DocumentServeRequest(
        space_id="1", doc_name="TestDocument", doc_type="DOCUMENT"
    )

    service.get = Mock(return_value=SpaceServeResponse(id=1, name="TestSpace"))
    service._document_dao.get_knowledge_documents = Mock(return_value=[])
    service._document_dao.create_knowledge_document = Mock(return_value="2")

    response = service.create_document(request)
    assert response == "2"


@pytest.mark.asyncio
async def test_delete_document(service):
    document_id = 2
    existing_document = DocumentServeResponse(
        id=document_id, space="TestSpace", vector_ids=None
    )

    service._document_dao.get_one = Mock(return_value=existing_document)
    service._dao.get_knowledge_space = Mock(
        return_value=[SpaceServeRequest(id="1", name="TestSpace")]
    )
    service._chunk_dao.raw_delete = Mock()
    service._document_dao.raw_delete = Mock(return_value=existing_document)

    response = service.delete_document(document_id)

    assert response.id == document_id
    service._chunk_dao.raw_delete.assert_called_once_with(document_id)
    service._document_dao.raw_delete.assert_called_once_with(existing_document)


# @pytest.mark.asyncio
# async def test_batch_document_sync_success(service):
#     space_id = "test_space_id"
#     chunk_parameters=ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
#     sync_request = KnowledgeSyncRequest(doc_id=1,
#                                         chunk_parameters=chunk_parameters)
#
#     # Mocking document retrieval
#     doc_mock = MagicMock()
#     doc_mock.status = SyncStatus.TODO.name  # Mock an initial status
#     doc_mock.id = 1
#     doc_mock.doc_name = "Test Document"
#
#     service._document_dao.documents_by_ids.return_value = [
#         doc_mock]  # Mocking the response
#
#     # Setting mock for chunk strategies
#     sync_request.chunk_parameters.chunk_strategy = "CHUNK_BY_SIZE"
#
#     # Run the test asynchronously
#     doc_ids = await service._batch_document_sync(space_id, [sync_request])
#
#     service._sync_knowledge_document.assert_awaited_once_with(
#         space_id,
#         doc_mock,
#         sync_request.chunk_parameters
#     )
