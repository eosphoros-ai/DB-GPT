import click
import functools
import logging
import os
from typing import Callable, List, Type

from pilot.model.controller.controller import ModelRegistryClient
from pilot.configs.model_config import LOGDIR
from pilot.model.base import WorkerApplyType
from pilot.model.parameter import (
    ModelControllerParameters,
    ModelWorkerParameters,
    ModelParameters,
)
from pilot.utils import get_or_create_event_loop
from pilot.utils.parameter_utils import EnvArgumentParser
from pilot.utils.command_utils import _run_current_with_daemon, _stop_service


MODEL_CONTROLLER_ADDRESS = "http://127.0.0.1:8000"

logger = logging.getLogger("dbgpt_cli")


@click.group("model")
@click.option(
    "--address",
    type=str,
    default=None,
    required=False,
    show_default=True,
    help=(
        "Address of the Model Controller to connect to. "
        "Just support light deploy model, If the environment variable CONTROLLER_ADDRESS is configured, read from the environment variable"
    ),
)
def model_cli_group(address: str):
    """Clients that manage model serving"""
    global MODEL_CONTROLLER_ADDRESS
    if not address:
        from pilot.utils.command_utils import _detect_controller_address

        MODEL_CONTROLLER_ADDRESS = _detect_controller_address()
    else:
        MODEL_CONTROLLER_ADDRESS = address


@model_cli_group.command()
@click.option(
    "--model_name", type=str, default=None, required=False, help=("The name of model")
)
@click.option(
    "--model_type", type=str, default="llm", required=False, help=("The type of model")
)
def list(model_name: str, model_type: str):
    """List model instances"""
    from prettytable import PrettyTable

    loop = get_or_create_event_loop()
    registry = ModelRegistryClient(MODEL_CONTROLLER_ADDRESS)

    if not model_name:
        instances = loop.run_until_complete(registry.get_all_model_instances())
    else:
        if not model_type:
            model_type = "llm"
        register_model_name = f"{model_name}@{model_type}"
        instances = loop.run_until_complete(
            registry.get_all_instances(register_model_name)
        )
    table = PrettyTable()

    table.field_names = [
        "Model Name",
        "Model Type",
        "Host",
        "Port",
        "Healthy",
        "Enabled",
        "Prompt Template",
        "Last Heartbeat",
    ]
    for instance in instances:
        model_name, model_type = instance.model_name.split("@")
        table.add_row(
            [
                model_name,
                model_type,
                instance.host,
                instance.port,
                instance.healthy,
                instance.enabled,
                instance.prompt_template,
                instance.last_heartbeat,
            ]
        )

    print(table)


def add_model_options(func):
    @click.option(
        "--model_name",
        type=str,
        default=None,
        required=True,
        help=("The name of model"),
    )
    @click.option(
        "--model_type",
        type=str,
        default="llm",
        required=False,
        help=("The type of model"),
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@model_cli_group.command()
@add_model_options
def stop(model_name: str, model_type: str):
    """Stop model instances"""
    worker_apply(MODEL_CONTROLLER_ADDRESS, model_name, model_type, WorkerApplyType.STOP)


@model_cli_group.command()
@add_model_options
def start(model_name: str, model_type: str):
    """Start model instances"""
    worker_apply(
        MODEL_CONTROLLER_ADDRESS, model_name, model_type, WorkerApplyType.START
    )


@model_cli_group.command()
@add_model_options
def restart(model_name: str, model_type: str):
    """Restart model instances"""
    worker_apply(
        MODEL_CONTROLLER_ADDRESS, model_name, model_type, WorkerApplyType.RESTART
    )


@model_cli_group.command()
@click.option(
    "--model_name",
    type=str,
    default=None,
    required=True,
    help=("The name of model"),
)
@click.option(
    "--system",
    type=str,
    default=None,
    required=False,
    help=("System prompt"),
)
def chat(model_name: str, system: str):
    """Interact with your bot from the command line"""
    _cli_chat(MODEL_CONTROLLER_ADDRESS, model_name, system)


# @model_cli_group.command()
# @add_model_options
# def modify(address: str, model_name: str, model_type: str):
#     """Restart model instances"""
#     worker_apply(address, model_name, model_type, WorkerApplyType.UPDATE_PARAMS)


def _get_worker_manager(address: str):
    from pilot.model.worker.manager import RemoteWorkerManager, WorkerApplyRequest

    registry = ModelRegistryClient(address)
    worker_manager = RemoteWorkerManager(registry)
    return worker_manager


def worker_apply(
    address: str, model_name: str, model_type: str, apply_type: WorkerApplyType
):
    from pilot.model.worker.manager import WorkerApplyRequest

    loop = get_or_create_event_loop()
    worker_manager = _get_worker_manager(address)
    apply_req = WorkerApplyRequest(
        model=model_name, worker_type=model_type, apply_type=apply_type
    )
    res = loop.run_until_complete(worker_manager.worker_apply(apply_req))
    print(res)


def _cli_chat(address: str, model_name: str, system_prompt: str = None):
    loop = get_or_create_event_loop()
    worker_manager = worker_manager = _get_worker_manager(address)
    loop.run_until_complete(_chat_stream(worker_manager, model_name, system_prompt))


async def _chat_stream(worker_manager, model_name: str, system_prompt: str = None):
    from pilot.model.worker.manager import PromptRequest
    from pilot.scene.base_message import ModelMessage, ModelMessageRoleType

    print(f"Chatbot started with model {model_name}. Type 'exit' to leave the chat.")
    hist = []
    previous_response = ""
    if system_prompt:
        hist.append(
            ModelMessage(role=ModelMessageRoleType.SYSTEM, content=system_prompt)
        )
    while True:
        previous_response = ""
        user_input = input("\n\nYou: ")
        if user_input.lower().strip() == "exit":
            break
        hist.append(ModelMessage(role=ModelMessageRoleType.HUMAN, content=user_input))
        request = PromptRequest(messages=hist, model=model_name, prompt="", echo=False)
        request = request.dict(exclude_none=True)
        print("Bot: ", end="")
        async for response in worker_manager.generate_stream(request):
            incremental_output = response.text[len(previous_response) :]
            print(incremental_output, end="", flush=True)
            previous_response = response.text
        hist.append(
            ModelMessage(role=ModelMessageRoleType.AI, content=previous_response)
        )


def add_stop_server_options(func):
    @click.option(
        "--port",
        type=int,
        default=None,
        required=False,
        help=("The port to stop"),
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@click.command(name="controller")
@EnvArgumentParser.create_click_option(ModelControllerParameters)
def start_model_controller(**kwargs):
    """Start model controller"""

    from pilot.model.controller.controller import run_model_controller

    if kwargs["daemon"]:
        log_file = os.path.join(LOGDIR, "model_controller_uvicorn.log")
        _run_current_with_daemon("ModelController", log_file)
    else:
        from pilot.model.controller.controller import run_model_controller

        run_model_controller()


@click.command(name="controller")
@add_stop_server_options
def stop_model_controller(port: int):
    """Start model controller"""
    # Command fragments to check against running processes
    _stop_service("controller", "ModelController", port=port)


def _model_dynamic_factory() -> Callable[[None], List[Type]]:
    from pilot.model.adapter import _dynamic_model_parser

    param_class = _dynamic_model_parser()
    fix_class = [ModelWorkerParameters]
    if not param_class:
        param_class = [ModelParameters]
    fix_class += param_class
    return fix_class


@click.command(name="worker")
@EnvArgumentParser.create_click_option(
    ModelWorkerParameters, ModelParameters, _dynamic_factory=_model_dynamic_factory
)
def start_model_worker(**kwargs):
    """Start model worker"""
    if kwargs["daemon"]:
        port = kwargs["port"]
        model_type = kwargs.get("worker_type") or "llm"
        log_file = os.path.join(LOGDIR, f"model_worker_{model_type}_{port}_uvicorn.log")
        _run_current_with_daemon("ModelWorker", log_file)
    else:
        from pilot.model.worker.manager import run_worker_manager

        run_worker_manager()


@click.command(name="worker")
@add_stop_server_options
def stop_model_worker(port: int):
    """Stop model worker"""
    name = "ModelWorker"
    if port:
        name = f"{name}-{port}"
    _stop_service("worker", name, port=port)


@click.command(name="apiserver")
def start_apiserver(**kwargs):
    """Start apiserver(TODO)"""
    raise NotImplementedError


@click.command(name="apiserver")
def stop_apiserver(**kwargs):
    """Start apiserver(TODO)"""
    raise NotImplementedError


def _stop_all_model_server(**kwargs):
    """Stop all server"""
    _stop_service("worker", "ModelWorker")
    _stop_service("controller", "ModelController")
