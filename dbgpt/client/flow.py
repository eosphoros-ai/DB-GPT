"""this module contains the flow client functions."""
from typing import List

from dbgpt.core.awel.flow.flow_factory import FlowPanel
from dbgpt.core.schema.api import Result

from .client import Client, ClientException


async def create_flow(client: Client, flow: FlowPanel) -> FlowPanel:
    """Create a new flow.

    Args:
        client (Client): The dbgpt client.
        flow (FlowPanel): The flow panel.
    """
    try:
        res = await client.get("/awel/flows", flow.dict())
        result: Result = res.json()
        if result["success"]:
            return FlowPanel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to create flow: {e}")


async def update_flow(client: Client, flow: FlowPanel) -> FlowPanel:
    """Update a flow.

    Args:
        client (Client): The dbgpt client.
        flow (FlowPanel): The flow panel.
    Returns:
        FlowPanel: The flow panel.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.put("/awel/flows", flow.dict())
        result: Result = res.json()
        if result["success"]:
            return FlowPanel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to update flow: {e}")


async def delete_flow(client: Client, flow_id: str) -> FlowPanel:
    """
    Delete a flow.

    Args:
        client (Client): The dbgpt client.
        flow_id (str): The flow id.
    Returns:
        FlowPanel: The flow panel.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.delete("/awel/flows/" + flow_id)
        result: Result = res.json()
        if result["success"]:
            return FlowPanel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to delete flow: {e}")


async def get_flow(client: Client, flow_id: str) -> FlowPanel:
    """
    Get a flow.

    Args:
        client (Client): The dbgpt client.
        flow_id (str): The flow id.
    Returns:
        FlowPanel: The flow panel.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/awel/flows/" + flow_id)
        result: Result = res.json()
        if result["success"]:
            return FlowPanel(**result["data"])
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to get flow: {e}")


async def list_flow(client: Client) -> List[FlowPanel]:
    """
    List flows.

    Args:
        client (Client): The dbgpt client.
    Returns:
        List[FlowPanel]: The list of flow panels.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/awel/flows")
        result: Result = res.json()
        if result["success"]:
            return [FlowPanel(**flow) for flow in result["data"]["items"]]
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to list flows: {e}")
