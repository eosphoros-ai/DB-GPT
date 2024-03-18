"""this module contains the flow client functions."""
from dbgpt.client.client import Client
from dbgpt.core.awel.flow.flow_factory import FlowPanel


async def create_flow(client: Client, flow: FlowPanel):
    """Create a new flow.

    Args:
        client (Client): The dbgpt client.
        flow (FlowPanel): The flow panel.
    """
    return await client.get("/awel/flows", flow.dict())


async def update_flow(client: Client, flow: FlowPanel):
    """Update a flow.

    Args:
        client (Client): The dbgpt client.
        flow (FlowPanel): The flow panel.
    """
    return await client.put("/awel/flows", flow.dict())


async def delete_flow(client: Client, flow_id: str):
    """
    Delete a flow.

    Args:
        client (Client): The dbgpt client.
        flow_id (str): The flow id.
    """
    return await client.get("/awel/flows/" + flow_id)


async def get_flow(client: Client, flow_id: str):
    """
    Get a flow.

    Args:
        client (Client): The dbgpt client.
        flow_id (str): The flow id.
    """
    return await client.get("/awel/flows/" + flow_id)


async def list_flow(client: Client):
    """
    List flows.

    Args:
        client (Client): The dbgpt client.
    """
    return await client.get("/awel/flows")
