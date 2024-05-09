"""App Client API."""

from typing import List

from dbgpt.core.schema.api import Result

from .client import Client, ClientException
from .schema import AppModel


async def get_app(client: Client, app_id: str) -> AppModel:
    """Get an app.

    Args:
        client (Client): The dbgpt client.
        app_id (str): The app id.
    Returns:
        AppModel: The app model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/apps/" + app_id)
        result: Result = res.json()
        if result["success"]:
            return AppModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to get app: {e}")


async def list_app(client: Client) -> List[AppModel]:
    """List apps.

    Args:
        client (Client): The dbgpt client.
    Returns:
        List[AppModel]: The list of app models.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/apps")
        result: Result = res.json()
        if result["success"]:
            return [AppModel(**app) for app in result["data"]["app_list"]]
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to list apps: {e}")
