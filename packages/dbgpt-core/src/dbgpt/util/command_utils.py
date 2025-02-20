import os
import platform
import subprocess
import sys
from functools import lru_cache
from typing import List

import psutil


def _get_abspath_of_current_command(command_path: str) -> str:
    # If the command path is already an absolute path, return it as is
    if os.path.isabs(command_path):
        return command_path
    else:
        return os.path.abspath(command_path)


def _run_current_with_daemon(name: str, log_file: str) -> None:
    # Keep the script name and filter the parameters
    args = [sys.argv[0]] + [
        arg for arg in sys.argv[1:] if arg not in ("--daemon", "-d")
    ]
    args[0] = _get_abspath_of_current_command(args[0])

    # Open the log file
    log_handle = open(log_file, "a")

    # Build the command
    daemon_cmd = [sys.executable] + args

    kwargs = {
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
        "shell": False,
    }
    if platform.system().lower() == "windows":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["preexec_fn"] = os.setsid

    # Start the process
    try:
        process = subprocess.Popen(daemon_cmd, **kwargs)
        print(f"Started {name} in background with pid: {process.pid}")
    except Exception as e:
        log_handle.close()
        raise e


def _stop_service(
    key: str, fullname: str, service_keys: List[str] = None, port: int = None
):
    # Set default process identifier
    if service_keys is None:
        script_name = os.path.basename(sys.argv[0])
        service_keys = [script_name, "start", key]

    not_found = True

    # For each process, check if it matches the service_keys and port
    for proc_info in psutil.process_iter(attrs=["pid", "cmdline"]):
        try:
            # Get the command line arguments of the process
            cmdline = proc_info.info.get("cmdline") or []
            cmdline_str = " ".join(cmdline)

            # Check if all key fragments are in the cmdline
            if not all(fragment in cmdline_str for fragment in service_keys):
                continue

            proc = psutil.Process(proc_info.info["pid"])
            should_terminate = False

            # Check if the process is listening on the specified port
            if port is not None:
                try:
                    for conn in proc.connections():
                        if (
                            conn.status == psutil.CONN_LISTEN
                            and conn.laddr.port == port
                        ):
                            should_terminate = True
                            break
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            else:
                should_terminate = True

            # Terminate the process if it should be terminated
            if should_terminate:
                proc.terminate()
                message = (
                    f"Terminated the {fullname} with PID: {proc.pid} "
                    f"listening on port: {port}"
                    if port
                    else f"Terminated the {fullname} with PID: {proc.pid}"
                )
                print(message)
                not_found = False

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not_found:
        print(f"{fullname} process not found.")


def _get_ports_by_cmdline_part(service_keys: List[str]) -> List[int]:
    """
    Return a list of ports that are associated with processes that have all the
    service_keys in their cmdline.

    Args:
        service_keys (List[str]): List of strings that should all be present in the
            process's cmdline.

    Returns:
        List[int]: List of ports sorted with preference for 8000 and 5000, and then in
            ascending order.
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

    # Sort ports with preference for 8000 and 5670
    ports.sort(key=lambda x: (x != 8000, x != 5670, x))
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

    return "http://127.0.0.1:8000"
