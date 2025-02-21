"""this module contains the datasource client functions."""

from typing import List

from dbgpt._private.pydantic import model_to_dict
from dbgpt.core.schema.api import Result

from .client import Client, ClientException
from .schema import DatasourceModel


async def create_datasource(
    client: Client, datasource: DatasourceModel
) -> DatasourceModel:
    """Create a new datasource.

    Args:
        client (Client): The dbgpt client.
        datasource (DatasourceModel): The datasource model.
    """
    try:
        res = await client.get("/datasources", model_to_dict(datasource))
        result: Result = res.json()
        if result["success"]:
            return DatasourceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to create datasource: {e}")


async def update_datasource(
    client: Client, datasource: DatasourceModel
) -> DatasourceModel:
    """Update a datasource.

    Args:
        client (Client): The dbgpt client.
        datasource (DatasourceModel): The datasource model.
    Returns:
        DatasourceModel: The datasource model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.put("/datasources", model_to_dict(datasource))
        result: Result = res.json()
        if result["success"]:
            return DatasourceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to update datasource: {e}")


async def delete_datasource(client: Client, datasource_id: str) -> DatasourceModel:
    """
    Delete a datasource.

    Args:
        client (Client): The dbgpt client.
        datasource_id (str): The datasource id.
    Returns:
        DatasourceModel: The datasource model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.delete("/datasources/" + datasource_id)
        result: Result = res.json()
        if result["success"]:
            return DatasourceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to delete datasource: {e}")


async def get_datasource(client: Client, datasource_id: str) -> DatasourceModel:
    """
    Get a datasource.

    Args:
        client (Client): The dbgpt client.
        datasource_id (str): The datasource id.
    Returns:
        DatasourceModel: The datasource model.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/datasources/" + datasource_id)
        result: Result = res.json()
        if result["success"]:
            return DatasourceModel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to get datasource: {e}")


async def list_datasource(client: Client) -> List[DatasourceModel]:
    """
    List datasources.

    Args:
        client (Client): The dbgpt client.
    Returns:
        List[DatasourceModel]: The list of datasource models.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/datasources")
        result: Result = res.json()
        if result["success"]:
            return [DatasourceModel(**datasource) for datasource in result["data"]]
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to list datasource: {e}")
