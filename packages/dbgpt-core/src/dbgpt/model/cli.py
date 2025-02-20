import functools
import logging
import os
from typing import Callable, List, Optional, Type

import click

from dbgpt.configs.model_config import LOGDIR
from dbgpt.model.base import WorkerApplyType
from dbgpt.model.parameter import (
    BaseParameters,
    ModelWorkerParameters,
)
from dbgpt.util import get_or_create_event_loop
from dbgpt.util.command_utils import (
    _detect_controller_address,
    _run_current_with_daemon,
    _stop_service,
)
from dbgpt.util.console import CliLogger
from dbgpt.util.i18n_utils import _
from dbgpt.util.parameter_utils import (
    _build_parameter_class,
    build_lazy_click_command,
)

# Your can set environment variable CONTROLLER_ADDRESS to set the default address
MODEL_CONTROLLER_ADDRESS = "http://127.0.0.1:8000"

logger = logging.getLogger("dbgpt_cli")

cl = CliLogger()


def _get_worker_manager(address: str):
    from dbgpt.model.cluster import ModelRegistryClient, RemoteWorkerManager

    registry = ModelRegistryClient(address)
    worker_manager = RemoteWorkerManager(registry)
    return worker_manager


@click.group("model")
@click.option(
    "--address",
    type=str,
    default=None,
    required=False,
    show_default=True,
    help=(
        "Address of the Model Controller to connect to. "
        "Just support light deploy model, If the environment variable "
        "CONTROLLER_ADDRESS is configured, read from the environment variable"
    ),
)
def model_cli_group(address: str):
    """Clients that manage model serving"""
    global MODEL_CONTROLLER_ADDRESS
    if not address:
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

    from dbgpt.model.cluster import ModelRegistryClient

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
                instance.prompt_template if instance.prompt_template else "",
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
@click.option(
    "--host",
    type=str,
    required=True,
    help=("The remote host to stop model"),
)
@click.option(
    "--port",
    type=int,
    required=True,
    help=("The remote port to stop model"),
)
def stop(model_name: str, model_type: str, host: str, port: int):
    """Stop model instances"""
    from dbgpt.model.cluster import RemoteWorkerManager, WorkerStartupRequest

    worker_manager: RemoteWorkerManager = _get_worker_manager(MODEL_CONTROLLER_ADDRESS)
    req = WorkerStartupRequest(
        host=host,
        port=port,
        worker_type=model_type,
        model=model_name,
        params={},
    )
    loop = get_or_create_event_loop()
    res = loop.run_until_complete(worker_manager.model_shutdown(req))
    print(res)


def _remote_model_dynamic_factory() -> Callable[[None], List[Type]]:
    from dataclasses import dataclass, field

    from dbgpt.model.cluster import RemoteWorkerManager
    from dbgpt.model.parameter import WorkerType
    from dbgpt.util.parameter_utils import _SimpleArgParser

    pre_args = _SimpleArgParser("model_name", "address", "host", "port")
    pre_args.parse()
    model_name = pre_args.get("model_name")
    address = pre_args.get("address")
    host = pre_args.get("host")
    port = pre_args.get("port")
    if port:
        port = int(port)

    if not address:
        address = _detect_controller_address()

    worker_manager: RemoteWorkerManager = _get_worker_manager(address)
    loop = get_or_create_event_loop()
    models = loop.run_until_complete(worker_manager.supported_models())

    fields_dict = {}
    fields_dict["model_name"] = (
        str,
        field(default=None, metadata={"help": "The model name to deploy"}),
    )
    fields_dict["host"] = (
        str,
        field(default=None, metadata={"help": "The remote host to deploy model"}),
    )
    fields_dict["port"] = (
        int,
        field(default=None, metadata={"help": "The remote port to deploy model"}),
    )
    result_class = dataclass(
        type("RemoteModelWorkerParameters", (object,), fields_dict)
    )

    if not models:
        return [result_class]

    valid_models = []
    valid_model_cls = []
    for model in models:
        if host and host != model.host:
            continue
        if port and port != model.port:
            continue
        valid_models += [m.model for m in model.models]
        valid_model_cls += [
            (m, _build_parameter_class(m.params)) for m in model.models if m.params
        ]
    real_model, real_params_cls = valid_model_cls[0]
    real_path = None
    real_worker_type = "llm"
    if model_name:
        params_cls_list = [m for m in valid_model_cls if m[0].model == model_name]
        if not params_cls_list:
            raise ValueError(f"Not supported model with model name: {model_name}")
        real_model, real_params_cls = params_cls_list[0]
        real_path = real_model.path
        real_worker_type = real_model.worker_type

    @dataclass
    class RemoteModelWorkerParameters(BaseParameters):
        model_name: str = field(
            metadata={"valid_values": valid_models, "help": "The model name to deploy"}
        )
        model_path: Optional[str] = field(
            default=real_path, metadata={"help": "The model path to deploy"}
        )
        host: Optional[str] = field(
            default=models[0].host,
            metadata={
                "valid_values": [model.host for model in models],
                "help": "The remote host to deploy model",
            },
        )

        port: Optional[int] = field(
            default=models[0].port,
            metadata={
                "valid_values": [model.port for model in models],
                "help": "The remote port to deploy model",
            },
        )
        worker_type: Optional[str] = field(
            default=real_worker_type,
            metadata={
                "valid_values": WorkerType.values(),
                "help": "Worker type",
            },
        )

    return [RemoteModelWorkerParameters, real_params_cls]


@model_cli_group.command(
    cls=build_lazy_click_command(_dynamic_factory=_remote_model_dynamic_factory)
)
def start(**kwargs):
    """Start model instances"""
    from dbgpt.model.cluster import RemoteWorkerManager, WorkerStartupRequest

    worker_manager: RemoteWorkerManager = _get_worker_manager(MODEL_CONTROLLER_ADDRESS)
    req = WorkerStartupRequest(
        host=kwargs["host"],
        port=kwargs["port"],
        worker_type=kwargs["worker_type"],
        model=kwargs["model_name"],
        params={},
    )
    del kwargs["host"]
    del kwargs["port"]
    del kwargs["worker_type"]
    req.params = kwargs
    loop = get_or_create_event_loop()
    res = loop.run_until_complete(worker_manager.model_startup(req))
    print(res)


@model_cli_group.command()
@add_model_options
def restart(model_name: str, model_type: str):
    """Restart model instances"""
    worker_apply(
        MODEL_CONTROLLER_ADDRESS, model_name, model_type, WorkerApplyType.RESTART
    )


@model_cli_group.command()
@click.option(
    "-m",
    "--model_name",
    type=str,
    default=None,
    required=True,
    help=_("The name of model"),
)
@click.option(
    "--system",
    type=str,
    default=None,
    required=False,
    help=_("System prompt"),
)
def chat(model_name: str, system: str):
    """Interact with your bot from the command line"""
    _cli_chat(MODEL_CONTROLLER_ADDRESS, model_name, system)


def worker_apply(
    address: str, model_name: str, model_type: str, apply_type: WorkerApplyType
):
    from dbgpt.model.cluster import WorkerApplyRequest

    loop = get_or_create_event_loop()
    worker_manager = _get_worker_manager(address)
    apply_req = WorkerApplyRequest(
        model=model_name, worker_type=model_type, apply_type=apply_type
    )
    res = loop.run_until_complete(worker_manager.worker_apply(apply_req))
    print(res)


def _cli_chat(address: str, model_name: str, system_prompt: str = None):
    loop = get_or_create_event_loop()
    worker_manager = _get_worker_manager(address)
    loop.run_until_complete(_chat_stream(worker_manager, model_name, system_prompt))


async def _chat_stream(
    worker_manager,
    model_name: str,
    system_prompt: str = None,
):
    import os
    import readline

    from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
    from dbgpt.model.cluster import PromptRequest

    # Set up readline for history
    histfile = os.path.join(os.path.expanduser("~"), ".dbgpt_cli_chat_history")
    try:
        readline.read_history_file(histfile)
        readline.set_history_length(1000)
    except FileNotFoundError:
        pass

    # Helper to clear screen
    def clear_screen():
        os.system("cls" if os.name == "nt" else "clear")

    clear_screen()
    cl.print(f"📢 Chatbot started with model {model_name}")
    cl.print(
        "Commands: /exit to leave, /clear to clear screen, /reset to reset conversation"
    )

    hist = []
    previous_response = ""

    if system_prompt:
        hist.append(
            ModelMessage(role=ModelMessageRoleType.SYSTEM, content=system_prompt)
        )

    while True:
        previous_response = ""
        try:
            print("\n")  # Add extra line break for clarity
            user_input = input("You: ")
        except UnicodeDecodeError:
            cl.error("\n⚠️ Error reading input. Please try again.")
            continue

        # Handle commands
        if user_input.lower().strip() == "/exit":
            cl.info("\nGoodbye! 👋")
            break
        elif user_input.lower().strip() == "/clear":
            clear_screen()
            continue
        elif user_input.lower().strip() == "/reset":
            hist = []
            if system_prompt:
                hist.append(
                    ModelMessage(
                        role=ModelMessageRoleType.SYSTEM, content=system_prompt
                    )
                )
            clear_screen()
            cl.info("Conversation has been reset!")
            continue
        elif not user_input.strip():
            continue

        hist.append(ModelMessage(role=ModelMessageRoleType.HUMAN, content=user_input))
        request = PromptRequest(messages=hist, model=model_name, prompt="", echo=False)
        request = request.dict(exclude_none=True)

        cl.print("Bot: ", end="")
        try:
            async for response in worker_manager.generate_stream(request):
                incremental_output = response.text[len(previous_response) :]
                # print(incremental_output, end="", flush=True)
                cl.print(incremental_output, end="")
                previous_response = response.text
            hist.append(
                ModelMessage(role=ModelMessageRoleType.AI, content=previous_response)
            )
        except Exception as e:
            cl.error(f"\n⚠️ Error: {str(e)}")

    # Save history
    try:
        readline.write_history_file(histfile)
    except Exception as _e:
        pass


def add_start_server_options(func):
    @click.option(
        "-c",
        "--config",
        type=str,
        required=True,
        help=(_("The config file to start server")),
    )
    @click.option(
        "-d",
        "--daemon",
        is_flag=True,
        help=(
            _(
                "Run in daemon mode. It will run in the background. If you want to stop"
                " it, use `dbgpt stop` command"
            )
        ),
    )
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


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
@add_start_server_options
def start_model_controller(config: str, **kwargs):
    """Start model controller"""

    if "daemon" in kwargs and kwargs["daemon"]:
        log_file = os.path.join(LOGDIR, "model_controller_uvicorn.log")
        _run_current_with_daemon("ModelController", log_file)
    else:
        from dbgpt.model.cluster import run_model_controller

        run_model_controller(config)


@click.command(name="controller")
@add_stop_server_options
def stop_model_controller(port: int):
    """Start model controller"""
    # Command fragments to check against running processes
    _stop_service("controller", "ModelController", port=port)


def _model_dynamic_factory() -> Callable[[None], List[Type]]:
    from dbgpt.model.adapter.model_adapter import _dynamic_model_parser

    param_class = _dynamic_model_parser()
    fix_class = [ModelWorkerParameters]
    if not param_class:
        # param_class = [ModelParameters]
        param_class = []
    fix_class += param_class
    return fix_class


@click.command(name="worker")
@add_start_server_options
def start_model_worker(config: str, **kwargs):
    """Start model worker"""
    if kwargs["daemon"]:
        port = kwargs["port"]
        model_type = kwargs.get("worker_type") or "llm"
        log_file = os.path.join(LOGDIR, f"model_worker_{model_type}_{port}_uvicorn.log")
        _run_current_with_daemon("ModelWorker", log_file)
    else:
        from dbgpt.model.cluster import run_worker_manager

        run_worker_manager(config)


@click.command(name="worker")
@add_stop_server_options
def stop_model_worker(port: Optional[int] = None):
    """Stop model worker"""
    name = "ModelWorker"
    if port:
        name = f"{name}-{port}"
    _stop_service("worker", name, port=port)


@click.command(name="apiserver")
@add_start_server_options
def start_apiserver(config: str, **kwargs):
    """Start apiserver"""

    if kwargs["daemon"]:
        log_file = os.path.join(LOGDIR, "model_apiserver_uvicorn.log")
        _run_current_with_daemon("ModelAPIServer", log_file)
    else:
        from dbgpt.model.cluster import run_apiserver

        run_apiserver(config)


@click.command(name="apiserver")
@add_stop_server_options
def stop_apiserver(port: int):
    """Stop apiserver"""
    name = "ModelAPIServer"
    if port:
        name = f"{name}-{port}"
    _stop_service("apiserver", name, port=port)


def _stop_all_model_server(**kwargs):
    """Stop all server"""
    _stop_service("worker", "ModelWorker")
    _stop_service("controller", "ModelController")
    _stop_service("apiserver", "ModelAPIServer")
