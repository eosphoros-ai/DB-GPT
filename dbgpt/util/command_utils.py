import sys
import os
import subprocess
from typing import List, Dict
import psutil
import platform
from functools import lru_cache


def _get_abspath_of_current_command(command_path: str):
    if not command_path.endswith(".py"):
        return command_path
    # This implementation is very ugly
    command_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts",
        "cli_scripts.py",
    )
    return command_path


def _run_current_with_daemon(name: str, log_file: str):
    # Get all arguments except for --daemon
    args = [arg for arg in sys.argv if arg != "--daemon" and arg != "-d"]
    args[0] = _get_abspath_of_current_command(args[0])

    daemon_cmd = [sys.executable] + args
    daemon_cmd = " ".join(daemon_cmd)
    daemon_cmd += f" > {log_file} 2>&1"

    print(f"daemon cmd: {daemon_cmd}")
    # Check the platform and set the appropriate flags or functions
    if "windows" in platform.system().lower():
        process = subprocess.Popen(
            daemon_cmd,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
    else:  # macOS, Linux, and other Unix-like systems
        process = subprocess.Popen(
            daemon_cmd,
            preexec_fn=os.setsid,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )

    print(f"Started {name} in background with pid: {process.pid}")


def _run_current_with_gunicorn(app: str, config_path: str, kwargs: Dict):
    try:
        import gunicorn
    except ImportError as e:
        raise ValueError(
            "Could not import python package: gunicorn"
            "Daemon mode need install gunicorn, please install `pip install gunicorn`"
        ) from e

    from dbgpt.util.parameter_utils import EnvArgumentParser

    env_to_app = {}
    env_to_app.update(os.environ)
    app_env = EnvArgumentParser._kwargs_to_env_key_value(kwargs)
    env_to_app.update(app_env)
    cmd = f"uvicorn {app} --host 0.0.0.0 --port 5000"
    if "windows" in platform.system().lower():
        raise Exception("Not support on windows")
    else:  # macOS, Linux, and other Unix-like systems
        process = subprocess.Popen(cmd, shell=True, env=env_to_app)
    print(f"Started {app} with gunicorn in background with pid: {process.pid}")


def _stop_service(
    key: str, fullname: str, service_keys: List[str] = None, port: int = None
):
    if not service_keys:
        service_keys = [sys.argv[0], "start", key]
    not_found = True
    for process in psutil.process_iter(attrs=["pid", "datasource", "cmdline"]):
        try:
            cmdline = " ".join(process.info["cmdline"])

            # Check if all key fragments are in the cmdline
            if all(fragment in cmdline for fragment in service_keys):
                if port:
                    for conn in process.info["datasource"]:
                        if (
                            conn.status == psutil.CONN_LISTEN
                            and conn.laddr.port == port
                        ):
                            psutil.Process(process.info["pid"]).terminate()
                            print(
                                f"Terminated the {fullname} with PID: {process.info['pid']} listening on port: {port}"
                            )
                            not_found = False
                else:
                    psutil.Process(process.info["pid"]).terminate()
                    print(f"Terminated the {fullname} with PID: {process.info['pid']}")
                    not_found = False
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if not_found:
        print(f"{fullname} process not found.")


def _get_ports_by_cmdline_part(service_keys: List[str]) -> List[int]:
    """
    Return a list of ports that are associated with processes that have all the service_keys in their cmdline.

    Args:
        service_keys (List[str]): List of strings that should all be present in the process's cmdline.

    Returns:
        List[int]: List of ports sorted with preference for 8000 and 5000, and then in ascending order.
    """
    ports = []

    for process in psutil.process_iter(attrs=["pid", "name", "cmdline", "connections"]):
        try:
            # Convert the cmdline list to a single string for easier checking
            cmdline = ""
            if process.info.get("cmdline"):
                cmdline = " ".join(process.info["cmdline"])

            # Check if all the service keys are present in the cmdline
            if cmdline and all(fragment in cmdline for fragment in service_keys):
                connections = process.info.get("connections")
                if connections is not None and len(ports) == 0:
                    for connection in connections:
                        if connection.status == psutil.CONN_LISTEN:
                            ports.append(connection.laddr.port)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    # Sort ports with preference for 8000 and 5000
    ports.sort(key=lambda x: (x != 8000, x != 5000, x))
    return ports


@lru_cache()
def _detect_controller_address() -> str:
    controller_addr = os.getenv("CONTROLLER_ADDRESS")
    if controller_addr:
        return controller_addr

    cmdline_fragments = [
        ["python", "start", "controller"],
        ["python", "controller"],
        ["python", "start", "webserver"],
        ["python", "dbgpt_server"],
    ]

    for fragments in cmdline_fragments:
        ports = _get_ports_by_cmdline_part(fragments)
        if ports:
            return f"http://127.0.0.1:{ports[0]}"

    return f"http://127.0.0.1:8000"
