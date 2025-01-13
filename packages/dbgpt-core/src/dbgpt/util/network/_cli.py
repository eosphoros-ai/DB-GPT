import os
import socket
import ssl as py_ssl
import threading

import click

from ..console import CliLogger

logger = CliLogger()


def forward_data(source, destination):
    """Forward data from source to destination."""
    try:
        while True:
            data = source.recv(4096)
            if b"" == data:
                destination.sendall(data)
                break
            if not data:
                break  # no more data or connection closed
            destination.sendall(data)
    except Exception as e:
        logger.error(f"Error forwarding data: {e}")


def handle_client(
    client_socket,
    remote_host: str,
    remote_port: int,
    is_ssl: bool = False,
    http_proxy=None,
):
    """Handle client connection.

    Create a connection to the remote host and port, and forward data between the
    client and the remote host.

    Close the client socket and remote socket when all forwarding threads are done.
    """
    # remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if http_proxy:
        proxy_host, proxy_port = http_proxy
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.connect((proxy_host, proxy_port))
        client_ip = client_socket.getpeername()[0]
        scheme = "https" if is_ssl else "http"
        connect_request = (
            f"CONNECT {remote_host}:{remote_port} HTTP/1.1\r\n"
            f"Host: {remote_host}\r\n"
            f"Connection: keep-alive\r\n"
            f"X-Real-IP: {client_ip}\r\n"
            f"X-Forwarded-For: {client_ip}\r\n"
            f"X-Forwarded-Proto: {scheme}\r\n\r\n"
        )
        logger.info(f"Sending connect request: {connect_request}")
        remote_socket.sendall(connect_request.encode())

        response = b""
        while True:
            part = remote_socket.recv(4096)
            response += part
            if b"\r\n\r\n" in part:
                break

        if b"200 Connection established" not in response:
            logger.error("Failed to establish connection through proxy")
            return

    else:
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.connect((remote_host, remote_port))

    if is_ssl:
        # context = py_ssl.create_default_context(py_ssl.Purpose.CLIENT_AUTH)
        context = py_ssl.create_default_context(py_ssl.Purpose.SERVER_AUTH)
        # ssl_target_socket = py_ssl.wrap_socket(remote_socket)
        ssl_target_socket = context.wrap_socket(
            remote_socket, server_hostname=remote_host
        )
    else:
        ssl_target_socket = remote_socket
    try:
        # ssl_target_socket.connect((remote_host, remote_port))

        # Forward data from client to server
        client_to_server = threading.Thread(
            target=forward_data, args=(client_socket, ssl_target_socket)
        )
        client_to_server.start()

        # Forward data from server to client
        server_to_client = threading.Thread(
            target=forward_data, args=(ssl_target_socket, client_socket)
        )
        server_to_client.start()

        client_to_server.join()
        server_to_client.join()
    except Exception as e:
        logger.error(f"Error handling client connection: {e}")
    finally:
        # close the client and server sockets
        client_socket.close()
        ssl_target_socket.close()


@click.command(name="forward")
@click.option("--local-port", required=True, type=int, help="Local port to listen on.")
@click.option(
    "--remote-host", required=True, type=str, help="Remote host to forward to."
)
@click.option(
    "--remote-port", required=True, type=int, help="Remote port to forward to."
)
@click.option(
    "--ssl",
    is_flag=True,
    help="Whether to use SSL for the connection to the remote host.",
)
@click.option(
    "--tcp",
    is_flag=True,
    help="Whether to forward TCP traffic. "
    "Default is HTTP. TCP has higher performance but not support proxies now.",
)
@click.option("--timeout", type=int, default=120, help="Timeout for the connection.")
@click.option(
    "--proxies",
    type=str,
    help="HTTP proxy to use for forwarding requests. e.g. http://127.0.0.1:7890, "
    "if not specified, try to read from environment variable http_proxy and "
    "https_proxy.",
)
def start_forward(
    local_port,
    remote_host,
    remote_port,
    ssl: bool,
    tcp: bool,
    timeout: int,
    proxies: str | None = None,
):
    """Start a TCP/HTTP proxy server that forwards traffic from a local port to a remote
    host and port, just for debugging purposes, please don't use it in production
    environment.
    """

    """
    Example:
        1. Forward HTTP traffic:

        ```
        dbgpt net forward --local-port 5010 \
            --remote-host api.openai.com \
            --remote-port 443 \
            --ssl \
            --proxies http://127.0.0.1:7890 \
            --timeout 30    
        ```
        Then you can set your environment variable `OPENAI_API_BASE` to 
        `http://127.0.0.1:5010/v1`
    """
    if not tcp:
        _start_http_forward(local_port, remote_host, remote_port, ssl, timeout, proxies)
    else:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind(("0.0.0.0", local_port))
            server.listen(5)
            logger.info(
                f"[*] Listening on 0.0.0.0:{local_port}, forwarding to "
                f"{remote_host}:{remote_port}"
            )
            # http_proxy = ("127.0.0.1", 7890)
            proxies = (
                proxies or os.environ.get("http_proxy") or os.environ.get("https_proxy")
            )
            if proxies:
                # proxies = "http://127.0.0.1:7890"
                if proxies.startswith("http://") or proxies.startswith("https://"):
                    proxies = proxies.split("//")[1]
                http_proxy = proxies.split(":")[0], int(proxies.split(":")[1])

            while True:
                client_socket, addr = server.accept()
                logger.info(f"[*] Accepted connection from: {addr[0]}:{addr[1]}")
                client_thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, remote_host, remote_port, ssl, http_proxy),
                )
                client_thread.start()


def _start_http_forward(
    local_port, remote_host, remote_port, ssl: bool, timeout, proxies: str | None = None
):
    import httpx
    import uvicorn
    from fastapi import BackgroundTasks, Request, Response
    from fastapi.responses import StreamingResponse

    from dbgpt.util.fastapi import create_app

    app = create_app()

    @app.middleware("http")
    async def forward_http_request(request: Request, call_next):
        """Forward HTTP request to remote host."""
        nonlocal proxies
        req_body = await request.body()
        scheme = request.scope.get("scheme")
        path = request.scope.get("path")
        headers = dict(request.headers)
        # Remove needless headers
        stream_response = False
        if request.method in ["POST", "PUT"]:
            try:
                import json

                stream_config = json.loads(req_body.decode("utf-8"))
                stream_response = stream_config.get("stream", False)
            except Exception:
                pass
        headers.pop("host", None)
        if not proxies:
            proxies = os.environ.get("http_proxy") or os.environ.get("https_proxy")
        if proxies:
            client_req = {
                "proxies": {
                    "http://": proxies,
                    "https://": proxies,
                }
            }
        else:
            client_req = {}
        if timeout:
            client_req["timeout"] = timeout

        client = httpx.AsyncClient(**client_req)
        # async with httpx.AsyncClient(**client_req) as client:
        proxy_url = f"{remote_host}:{remote_port}"
        if ssl:
            scheme = "https"
        new_url = (
            proxy_url if "://" in proxy_url else (scheme + "://" + proxy_url + path)
        )
        req = client.build_request(
            method=request.method,
            url=new_url,
            cookies=request.cookies,
            content=req_body,
            headers=headers,
            params=request.query_params,
        )
        has_connection = False
        try:
            logger.info(f"Forwarding request to {new_url}")
            res = await client.send(req, stream=stream_response)
            has_connection = True
            if stream_response:
                res_headers = {
                    "Content-Type": "text/event-stream",
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Transfer-Encoding": "chunked",
                }
                background_tasks = BackgroundTasks()
                background_tasks.add_task(client.aclose)
                return StreamingResponse(
                    res.aiter_raw(),
                    headers=res_headers,
                    media_type=res.headers.get("content-type"),
                )
            else:
                return Response(
                    content=res.content,
                    status_code=res.status_code,
                    headers=dict(res.headers),
                )
        except httpx.ConnectTimeout:
            return Response(
                content="Connection to remote server timeout", status_code=500
            )
        except Exception as e:
            return Response(content=str(e), status_code=500)
        finally:
            if has_connection and not stream_response:
                await client.aclose()

    uvicorn.run(app, host="0.0.0.0", port=local_port)
