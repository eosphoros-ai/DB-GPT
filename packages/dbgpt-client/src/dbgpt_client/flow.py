"""this module contains the flow client functions."""

from typing import Any, Callable, Dict, List

from httpx import AsyncClient

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
        res = await client.get("/awel/flows", flow.to_dict())
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
        res = await client.put("/awel/flows", flow.to_dict())
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


async def list_flow(
    client: Client, name: str | None = None, uid: str | None = None
) -> List[FlowPanel]:
    """
    List flows.

    Args:
        client (Client): The dbgpt client.
        name (str): The name of the flow.
        uid (str): The uid of the flow.
    Returns:
        List[FlowPanel]: The list of flow panels.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/awel/flows", **{"name": name, "uid": uid})
        result: Result = res.json()
        if result["success"]:
            return [FlowPanel(**flow) for flow in result["data"]["items"]]
        else:
            raise ClientException(status=result["err_code"], reason=result)
    except Exception as e:
        raise ClientException(f"Failed to list flows: {e}")


async def run_flow_cmd(
    client: Client,
    name: str | None = None,
    uid: str | None = None,
    data: Dict[str, Any] | None = None,
    non_streaming_callback: Callable[[str], None] | None = None,
    streaming_callback: Callable[[str], None] | None = None,
) -> None:
    """
    Run flows.

    Args:
        client (Client): The dbgpt client.
        name (str): The name of the flow.
        uid (str): The uid of the flow.
        data (Dict[str, Any]): The data to run the flow.
        non_streaming_callback (Callable[[str], None]): The non-streaming callback.
        streaming_callback (Callable[[str], None]): The streaming callback.
    Returns:
        List[FlowPanel]: The list of flow panels.
    Raises:
        ClientException: If the request failed.
    """
    try:
        res = await client.get("/awel/flows", **{"name": name, "uid": uid})
        result: Result = res.json()
        if not result["success"]:
            raise ClientException("Flow not found with the given name or uid")
        flows = result["data"]["items"]
        if not flows:
            raise ClientException("Flow not found with the given name or uid")
        if len(flows) > 1:
            raise ClientException("More than one flow found")
        flow = flows[0]
        flow_panel = FlowPanel(**flow)
        metadata = flow.get("metadata")
        await _run_flow_trigger(
            client,
            flow_panel,
            metadata,
            data,
            non_streaming_callback=non_streaming_callback,
            streaming_callback=streaming_callback,
        )
    except Exception as e:
        raise ClientException(f"Failed to run flows: {e}")


async def _run_flow_trigger(
    client: Client,
    flow: FlowPanel,
    metadata: Dict[str, Any] | None = None,
    data: Dict[str, Any] | None = None,
    non_streaming_callback: Callable[[str], None] | None = None,
    streaming_callback: Callable[[str], None] | None = None,
):
    if not metadata:
        raise ClientException("No AWEL flow metadata found")
    if "triggers" not in metadata:
        raise ClientException("No triggers found in AWEL flow metadata")
    triggers = metadata["triggers"]
    if len(triggers) > 1:
        raise ClientException("More than one trigger found")
    trigger = triggers[0]
    sse_output = metadata.get("sse_output", False)
    streaming_output = metadata.get("streaming_output", False)
    trigger_type = trigger["trigger_type"]
    if trigger_type == "http":
        methods = trigger["methods"]
        if not methods:
            method = "GET"
        else:
            method = methods[0]
        path = trigger["path"]
        base_url = client._base_url()
        req_url = f"{base_url}{path}"
        if streaming_output:
            await _call_stream_request(
                client._http_client,
                method,
                req_url,
                sse_output,
                data,
                streaming_callback,
            )
        elif non_streaming_callback:
            await _call_non_stream_request(
                client._http_client, method, req_url, data, non_streaming_callback
            )
    else:
        raise ClientException(f"Invalid trigger type: {trigger_type}")


async def _call_non_stream_request(
    http_client: AsyncClient,
    method: str,
    base_url: str,
    data: Dict[str, Any] | None = None,
    non_streaming_callback: Callable[[str], None] | None = None,
):
    import httpx

    kwargs: Dict[str, Any] = {"url": base_url, "method": method}
    if method in ["POST", "PUT"]:
        kwargs["json"] = data
    else:
        kwargs["params"] = data
    response = await http_client.request(**kwargs)
    bytes_response_content = await response.aread()
    if response.status_code != 200:
        str_error_message = ""
        error_message = await response.aread()
        if error_message:
            str_error_message = error_message.decode("utf-8")
        raise httpx.RequestError(
            f"Request failed with status {response.status_code}, error_message: "
            f"{str_error_message}",
            request=response.request,
        )
    response_content = bytes_response_content.decode("utf-8")
    if non_streaming_callback:
        non_streaming_callback(response_content)
    return response_content


async def _call_stream_request(
    http_client: AsyncClient,
    method: str,
    base_url: str,
    sse_output: bool,
    data: Dict[str, Any] | None = None,
    streaming_callback: Callable[[str], None] | None = None,
):
    full_out = ""
    async for out in _stream_request(http_client, method, base_url, sse_output, data):
        if streaming_callback:
            streaming_callback(out)
        full_out += out
    return full_out


async def _stream_request(
    http_client: AsyncClient,
    method: str,
    base_url: str,
    sse_output: bool,
    data: Dict[str, Any] | None = None,
):
    import json

    from dbgpt.core.awel.util.chat_util import parse_openai_output

    kwargs: Dict[str, Any] = {"url": base_url, "method": method}
    if method in ["POST", "PUT"]:
        kwargs["json"] = data
    else:
        kwargs["params"] = data

    async with http_client.stream(**kwargs) as response:
        if response.status_code == 200:
            async for line in response.aiter_lines():
                if not line:
                    continue
                if sse_output:
                    out = parse_openai_output(line)
                    if not out.success:
                        raise ClientException(f"Failed to parse output: {out.text}")
                    yield out.text
                else:
                    yield line
        else:
            try:
                error = await response.aread()
                yield json.loads(error)
            except Exception as e:
                raise e
