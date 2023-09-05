import sys
import os
import subprocess
from typing import List, Dict
import psutil
import platform


def _run_current_with_daemon(name: str, log_file: str):
    # Get all arguments except for --daemon
    args = [arg for arg in sys.argv if arg != "--daemon" and arg != "-d"]
    daemon_cmd = [sys.executable] + args
    daemon_cmd = " ".join(daemon_cmd)
    daemon_cmd += f" > {log_file} 2>&1"

    # Check the platform and set the appropriate flags or functions
    if platform.system() == "Windows":
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

    from pilot.utils.parameter_utils import EnvArgumentParser

    env_to_app = {}
    env_to_app.update(os.environ)
    app_env = EnvArgumentParser._kwargs_to_env_key_value(kwargs)
    env_to_app.update(app_env)
    cmd = f"uvicorn {app} --host 0.0.0.0 --port 5000"
    if platform.system() == "Windows":
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
    for process in psutil.process_iter(attrs=["pid", "connections", "cmdline"]):
        try:
            cmdline = " ".join(process.info["cmdline"])

            # Check if all key fragments are in the cmdline
            if all(fragment in cmdline for fragment in service_keys):
                if port:
                    for conn in process.info["connections"]:
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
