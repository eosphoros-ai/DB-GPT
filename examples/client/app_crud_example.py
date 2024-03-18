import asyncio

from dbgpt.client.app import list_app
from dbgpt.client.client import Client

"""
Client: Simple App CRUD example
        
            This example demonstrates how to use the dbgpt client to get, list apps.
            Example:
            .. code-block:: python

                DBGPT_API_KEY = "dbgpt"
                client = Client(api_key=DBGPT_API_KEY)
                # 1. List all apps
                res = await list_app(client)
                # 2. Get an app
                res = await get_app(
                    client, app_id="bf1c7561-13fc-4fe0-bf5d-c22e724766a8"
                )
        
"""


async def main():
    # initialize client
    DBGPT_API_KEY = "dbgpt"
    client = Client(api_key=DBGPT_API_KEY)
    res = await list_app(client)
    print(res.json())


if __name__ == "__main__":
    asyncio.run(main())
