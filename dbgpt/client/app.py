from dbgpt.client.client import Client


async def get_app(client: Client, app_id: str):
    """Get an app.
    Args:
        client (Client): The dbgpt client.
        app_id (str): The app id.
    """
    return await client.get("/apps/" + app_id)


async def list_app(client: Client):
    """List apps.
    Args:
        client (Client): The dbgpt client.
    """
    return await client.get("/apps")
