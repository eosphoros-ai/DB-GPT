import click
import functools

from pilot.model.controller.registry import ModelRegistryClient
from pilot.model.worker.manager import (
    RemoteWorkerManager,
    WorkerApplyRequest,
    WorkerApplyType,
)
from pilot.utils import get_or_create_event_loop


@click.group("model")
def model_cli_group():
    pass


@model_cli_group.command()
@click.option(
    "--address",
    type=str,
    default="http://127.0.0.1:8000",
    required=False,
    help=(
        "Address of the Model Controller to connect to."
        "Just support light deploy model"
    ),
)
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
        "--address",
        type=str,
        default="http://127.0.0.1:8000",
        required=False,
        help=(
            "Address of the Model Controller to connect to."
            "Just support light deploy model"
        ),
    )
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
