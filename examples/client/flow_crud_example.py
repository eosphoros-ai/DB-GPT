"""Client: Simple Flow CRUD example

This example demonstrates how to use the dbgpt client to create, get, update, and
delete flows.

Example:
    .. code-block:: python

        DBGPT_API_KEY = "dbgpt"
        client = Client(api_key=DBGPT_API_KEY)
        # 1. Create a flow
        res = await create_flow(
            client,
            FlowPanel(name="test_flow", desc="for client flow", owner="dbgpt"),
        )
        # 2. Update a flow
        res = await update_flow(
            client,
            FlowPanel(name="test_flow", desc="for client flow333", owner="dbgpt"),
        )
        # 3. Delete a flow
        res = await delete_flow(client, flow_id="bf1c7561-13fc-4fe0-bf5d-c22e724766a8")
        # 4. Get a flow
        res = await get_flow(client, flow_id="bf1c7561-13fc-4fe0-bf5d-c22e724766a8")
        # 5. List all flows
        res = await list_flow(client)

"""
import asyncio

from dbgpt.client import Client
from dbgpt.client.flow import list_flow


async def main():
    # initialize client
    DBGPT_API_KEY = "dbgpt"
    client = Client(api_key=DBGPT_API_KEY)
    res = await list_flow(client)
    print(res)


if __name__ == "__main__":
    asyncio.run(main())
