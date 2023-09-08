import click
import os
from pilot.server.base import WebWerverParameters
from pilot.configs.model_config import LOGDIR
from pilot.utils.parameter_utils import EnvArgumentParser
from pilot.utils.command_utils import _run_current_with_daemon, _stop_service


@click.command(name="webserver")
@EnvArgumentParser.create_click_option(WebWerverParameters)
def start_webserver(**kwargs):
    """Start webserver(dbgpt_server.py)"""
    if kwargs["daemon"]:
        log_file = os.path.join(LOGDIR, "webserver_uvicorn.log")
        _run_current_with_daemon("WebServer", log_file)
    else:
        from pilot.server.dbgpt_server import run_webserver

        run_webserver(WebWerverParameters(**kwargs))


@click.command(name="webserver")
@click.option(
    "--port",
    type=int,
    default=None,
    required=False,
    help=("The port to stop"),
)
def stop_webserver(port: int):
    """Stop webserver(dbgpt_server.py)"""
    _stop_service("webserver", "WebServer", port=port)


def _stop_all_dbgpt_server():
    _stop_service("webserver", "WebServer")
