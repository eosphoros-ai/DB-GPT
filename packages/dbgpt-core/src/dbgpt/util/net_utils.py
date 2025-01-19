import errno
import socket
from typing import Set, Tuple


def _get_ip_address(address: str = "10.254.254.254:1") -> str:
    ip, port = address.split(":")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(0)
    curr_address = "127.0.0.1"
    try:
        # doesn't even have to be reachable
        s.connect((ip, int(port)))
        curr_address = s.getsockname()[0]
    except OSError as e:
        if e.errno == errno.ENETUNREACH:
            try:
                hostname = socket.getfqdn(socket.gethostname())
                curr_address = socket.gethostbyname(hostname)
            except Exception:
                pass
    finally:
        s.close()
    return curr_address


async def _async_get_free_port(
    port_range: Tuple[int, int], timeout: int, used_ports: Set[int]
):
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _get_free_port, port_range, timeout, used_ports
    )


def _get_free_port(port_range: Tuple[int, int], timeout: int, used_ports: Set[int]):
    import random

    available_ports = set(range(port_range[0], port_range[1] + 1)) - used_ports
    if not available_ports:
        raise RuntimeError("No available ports in the specified range")

    while available_ports:
        port = random.choice(list(available_ports))
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", port))
                used_ports.add(port)
                return port
        except OSError:
            available_ports.remove(port)

    raise RuntimeError("No available ports in the specified range")
