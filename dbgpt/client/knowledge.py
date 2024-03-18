"""Knowledge API client."""
import json

from dbgpt.client.client import Client
from dbgpt.client.schemas import DocumentModel, SpaceModel, SyncModel


async def create_space(client: Client, app_model: SpaceModel):
    """Create a new space.

    Args:
        client (Client): The dbgpt client.
        app_model (SpaceModel): The app model.
    """
    return await client.post("/knowledge/spaces", app_model.dict())


async def update_space(client: Client, app_model: SpaceModel):
    """Update a document.

    Args:
        client (Client): The dbgpt client.
        app_model (SpaceModel): The app model.
    """
    return await client.put("/knowledge/spaces", app_model.dict())


async def delete_space(client: Client, space_id: str):
    """Delete a space.

    Args:
        client (Client): The dbgpt client.
        app_id (str): The app id.
    """
    return await client.delete("/knowledge/spaces/" + space_id)


async def get_space(client: Client, space_id: str):
    """Get a document.

    Args:
        client (Client): The dbgpt client.
        app_id (str): The app id.
    """
    return await client.get("/knowledge/spaces/" + space_id)


async def list_space(client: Client):
    """List apps.

    Args:
        client (Client): The dbgpt client.
    """
    return await client.get("/knowledge/spaces")


async def create_document(client: Client, doc_model: DocumentModel):
    """Create a new space.

    Args:
        client (Client): The dbgpt client.
        doc_model (SpaceModel): The document model.
    """
    return await client.post_param("/knowledge/documents", doc_model.dict())


async def delete_document(client: Client, document_id: str):
    """Delete a document.

    Args:
        client (Client): The dbgpt client.
        app_id (str): The app id.
    """
    return await client.delete("/knowledge/documents/" + document_id)


async def get_document(client: Client, document_id: str):
    """Get a document.

    Args:
        client (Client): The dbgpt client.
        app_id (str): The app id.
    """
    return await client.get("/knowledge/documents/" + document_id)


async def list_document(client: Client):
    """List documents.

    Args:
        client (Client): The dbgpt client.
    """
    return await client.get("/knowledge/documents")


async def sync_document(client: Client, sync_model: SyncModel):
    """Sync document.

    Args:
        client (Client): The dbgpt client.
    """
    return await client.post(
        "/knowledge/documents/sync", [json.loads(sync_model.json())]
    )
