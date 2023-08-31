import click
import functools

from pilot.model.controller.registry import ModelRegistryClient
from pilot.model.worker.manager import (
    RemoteWorkerManager,
    WorkerApplyRequest,
    WorkerApplyType,
)
from pilot.model.parameter import (
    ModelControllerParameters,
    ModelWorkerParameters,
    ModelParameters,
)
from pilot.utils import get_or_create_event_loop
from pilot.utils.parameter_utils import EnvArgumentParser


@click.group("model")
@click.option(
    "--address",
    type=str,
    default="http://127.0.0.1:8000",
    required=False,
    show_default=True,
    help=(
        "Address of the Model Controller to connect to. "
        "Just support light deploy model"
    ),
)
def model_cli_group():
    """Clients that manage model serving"""
    pass


@model_cli_group.command()
@click.option(
    "--model-name", type=str, default=None, required=False, help=("The name of model")
)
@click.option(
    "--model-type", type=str, default="llm", required=False, help=("The type of model")
)
def list(address: str, model_name: str, model_type: str):
    """List model instances"""
    from prettytable import PrettyTable

    loop = get_or_create_event_loop()
    registry = ModelRegistryClient(address)

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
        "--model-name",
        type=str,
        default=None,
        required=True,
        help=("The name of model"),
    )
    @click.option(
        "--model-type",
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
def stop(address: str, model_name: str, model_type: str):
    """Stop model instances"""
    worker_apply(address, model_name, model_type, WorkerApplyType.STOP)


@model_cli_group.command()
@add_model_options
def start(address: str, model_name: str, model_type: str):
    """Start model instances"""
    worker_apply(address, model_name, model_type, WorkerApplyType.START)


@model_cli_group.command()
@add_model_options
def restart(address: str, model_name: str, model_type: str):
    """Restart model instances"""
    worker_apply(address, model_name, model_type, WorkerApplyType.RESTART)


# @model_cli_group.command()
# @add_model_options
# def modify(address: str, model_name: str, model_type: str):
#     """Restart model instances"""
#     worker_apply(address, model_name, model_type, WorkerApplyType.UPDATE_PARAMS)


def worker_apply(
    address: str, model_name: str, model_type: str, apply_type: WorkerApplyType
):
    loop = get_or_create_event_loop()
    registry = ModelRegistryClient(address)
    worker_manager = RemoteWorkerManager(registry)
    apply_req = WorkerApplyRequest(
        model=model_name, worker_type=model_type, apply_type=apply_type
    )
    res = loop.run_until_complete(worker_manager.worker_apply(apply_req))
    print(res)


@click.command(name="controller")
@EnvArgumentParser.create_click_option(ModelControllerParameters)
def start_model_controller(**kwargs):
    """Start model controller"""
    from pilot.model.controller.controller import run_model_controller

    run_model_controller()


@click.command(name="controller")
def stop_model_controller(**kwargs):
    """Start model controller"""
    raise NotImplementedError


@click.command(name="worker")
@EnvArgumentParser.create_click_option(ModelWorkerParameters, ModelParameters)
def start_model_worker(**kwargs):
    """Start model worker"""
    from pilot.model.worker.manager import run_worker_manager

    run_worker_manager()


@click.command(name="worker")
def stop_model_worker(**kwargs):
    """Stop model worker"""
    raise NotImplementedError


@click.command(name="webserver")
def start_webserver(**kwargs):
    """Start webserver(dbgpt_server.py)"""
    raise NotImplementedError


@click.command(name="webserver")
def stop_webserver(**kwargs):
    """Stop webserver(dbgpt_server.py)"""
    raise NotImplementedError


@click.command(name="apiserver")
def start_apiserver(**kwargs):
    """Start apiserver(TODO)"""
    raise NotImplementedError


@click.command(name="controller")
def stop_apiserver(**kwargs):
    """Start apiserver(TODO)"""
    raise NotImplementedError
