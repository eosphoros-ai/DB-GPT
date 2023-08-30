import socket
import errno


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
        IP = "127.0.0.1"
        if e.errno == errno.ENETUNREACH:
            try:
                hostname = socket.getfqdn(socket.gethostname())
                curr_address = socket.gethostbyname(hostname)
            except Exception:
                pass
    finally:
        s.close()
    return curr_address
