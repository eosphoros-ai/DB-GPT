"""Knowledge API client."""
import json
from typing import List

from dbgpt.core.schema.api import Result

from .client import Client, ClientException
from .schema import DocumentModel, SpaceModel, SyncModel


async def create_space(client: Client, space_model: SpaceModel) -> SpaceModel:
    """Create a new space.

    Args:
        client (Client): The dbgpt client.
        space_model (SpaceModel): The space model.
    Returns:
        SpaceModel: The space model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.post("/knowledge/spaces", space_model.dict())
        result: Result = res.json()
        if result["success"]:
            return SpaceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to create space: {e}")


async def update_space(client: Client, space_model: SpaceModel) -> SpaceModel:
    """Update a document.

    Args:
        client (Client): The dbgpt client.
        space_model (SpaceModel): The space model.
    Returns:
        SpaceModel: The space model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.put("/knowledge/spaces", space_model.dict())
        result: Result = res.json()
        if result["success"]:
            return SpaceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to update space: {e}")


async def delete_space(client: Client, space_id: str) -> SpaceModel:
    """Delete a space.

    Args:
        client (Client): The dbgpt client.
        space_id (str): The space id.
    Returns:
        SpaceModel: The space model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.delete("/knowledge/spaces/" + space_id)
        result: Result = res.json()
        if result["success"]:
            return SpaceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to delete space: {e}")


async def get_space(client: Client, space_id: str) -> SpaceModel:
    """Get a document.

    Args:
        client (Client): The dbgpt client.
        space_id (str): The space id.
    Returns:
        SpaceModel: The space model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/knowledge/spaces/" + space_id)
        result: Result = res.json()
        if result["success"]:
            return SpaceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to get space: {e}")


async def list_space(client: Client) -> List[SpaceModel]:
    """List spaces.

    Args:
        client (Client): The dbgpt client.
    Returns:
        List[SpaceModel]: The list of space models.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/knowledge/spaces")
        result: Result = res.json()
        if result["success"]:
            return [SpaceModel(**space) for space in result["data"]["items"]]
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to list spaces: {e}")


async def create_document(client: Client, doc_model: DocumentModel) -> DocumentModel:
    """Create a new document.

    Args:
        client (Client): The dbgpt client.
        doc_model (SpaceModel): The document model.

    """
    try:
        res = await client.post_param("/knowledge/documents", doc_model.dict())
        result: Result = res.json()
        if result["success"]:
            return DocumentModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to create document: {e}")


async def delete_document(client: Client, document_id: str) -> DocumentModel:
    """Delete a document.

    Args:
        client (Client): The dbgpt client.
        document_id (str): The document id.
    Returns:
        DocumentModel: The document model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.delete("/knowledge/documents/" + document_id)
        result: Result = res.json()
        if result["success"]:
            return DocumentModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to delete document: {e}")


async def get_document(client: Client, document_id: str) -> DocumentModel:
    """Get a document.

    Args:
        client (Client): The dbgpt client.
        document_id (str): The document id.
    Returns:
        DocumentModel: The document model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/knowledge/documents/" + document_id)
        result: Result = res.json()
        if result["success"]:
            return DocumentModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to get document: {e}")


async def list_document(client: Client) -> List[DocumentModel]:
    """List documents.

    Args:
        client (Client): The dbgpt client.
    """
    try:
        res = await client.get("/knowledge/documents")
        result: Result = res.json()
        if result["success"]:
            return [DocumentModel(**document) for document in result["data"]["items"]]
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to list documents: {e}")


async def sync_document(client: Client, sync_model: SyncModel) -> List:
    """Sync document.

    Args:
        client (Client): The dbgpt client.
        sync_model (SyncModel): The sync model.
    Returns:
        List: The list of document ids.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.post(
            "/knowledge/documents/sync", [json.loads(sync_model.json())]
        )
        result: Result = res.json()
        if result["success"]:
            return result["data"]
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to list documents: {e}")
