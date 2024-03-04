"""Agentic Workflow Expression Language (AWEL).

Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow
expression language specially designed for large model application development. It
provides great functionality and flexibility. Through the AWEL API, you can focus on
the development of business logic for LLMs applications without paying attention to
cumbersome model and environment details.

"""

import logging
from typing import List, Optional

from dbgpt.component import SystemApp

from .dag.base import DAG, DAGContext, DAGVar
from .operators.base import BaseOperator, WorkflowRunner
from .operators.common_operator import (
    BranchFunc,
    BranchOperator,
    InputOperator,
    JoinOperator,
    MapOperator,
    ReduceStreamOperator,
    TriggerOperator,
)
from .operators.stream_operator import (
    StreamifyAbsOperator,
    TransformStreamAbsOperator,
    UnstreamifyAbsOperator,
)
from .runner.local_runner import DefaultWorkflowRunner
from .task.base import (
    InputContext,
    InputSource,
    TaskContext,
    TaskOutput,
    TaskState,
    is_empty_data,
)
from .task.task_impl import (
    BaseInputSource,
    DefaultInputContext,
    DefaultTaskContext,
    SimpleCallDataInputSource,
    SimpleInputSource,
    SimpleStreamTaskOutput,
    SimpleTaskOutput,
    _is_async_iterator,
)
from .trigger.base import Trigger
from .trigger.http_trigger import (
    CommonLLMHttpRequestBody,
    CommonLLMHTTPRequestContext,
    CommonLLMHttpResponseBody,
    HttpTrigger,
)

_request_http_trigger_available = False
try:
    # Optional import
    from .trigger.ext_http_trigger import RequestHttpTrigger  # noqa: F401

    _request_http_trigger_available = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

__all__ = [
    "initialize_awel",
    "DAGContext",
    "DAG",
    "DAGVar",
    "BaseOperator",
    "JoinOperator",
    "ReduceStreamOperator",
    "TriggerOperator",
    "MapOperator",
    "BranchOperator",
    "InputOperator",
    "BranchFunc",
    "WorkflowRunner",
    "TaskState",
    "is_empty_data",
    "TaskOutput",
    "TaskContext",
    "InputContext",
    "InputSource",
    "DefaultWorkflowRunner",
    "SimpleInputSource",
    "BaseInputSource",
    "SimpleCallDataInputSource",
    "DefaultTaskContext",
    "DefaultInputContext",
    "SimpleTaskOutput",
    "SimpleStreamTaskOutput",
    "StreamifyAbsOperator",
    "UnstreamifyAbsOperator",
    "TransformStreamAbsOperator",
    "Trigger",
    "HttpTrigger",
    "CommonLLMHTTPRequestContext",
    "CommonLLMHttpResponseBody",
    "CommonLLMHttpRequestBody",
    "setup_dev_environment",
    "_is_async_iterator",
]

if _request_http_trigger_available:
    __all__.append("RequestHttpTrigger")


def initialize_awel(system_app: SystemApp, dag_dirs: List[str]):
    """Initialize AWEL."""
    from .dag.dag_manager import DAGManager
    from .operators.base import initialize_runner
    from .trigger.trigger_manager import DefaultTriggerManager

    DAGVar.set_current_system_app(system_app)

    system_app.register(DefaultTriggerManager)
    dag_manager = DAGManager(system_app, dag_dirs)
    system_app.register_instance(dag_manager)
    initialize_runner(DefaultWorkflowRunner())


def setup_dev_environment(
    dags: List[DAG],
    host: str = "127.0.0.1",
    port: int = 5555,
    logging_level: Optional[str] = None,
    logger_filename: Optional[str] = None,
    show_dag_graph: Optional[bool] = True,
) -> None:
    """Run AWEL in development environment.

    Just using in development environment, not production environment.

    Args:
        dags (List[DAG]): The DAGs.
        host (Optional[str], optional): The host. Defaults to "127.0.0.1"
        port (Optional[int], optional): The port. Defaults to 5555.
        logging_level (Optional[str], optional): The logging level. Defaults to None.
        logger_filename (Optional[str], optional): The logger filename.
            Defaults to None.
        show_dag_graph (Optional[bool], optional): Whether show the DAG graph.
            Defaults to True. If True, the DAG graph will be saved to a file and open
            it automatically.
    """
    from dbgpt.component import SystemApp
    from dbgpt.util.utils import setup_logging

    from .trigger.trigger_manager import DefaultTriggerManager

    if not logger_filename:
        logger_filename = "dbgpt_awel_dev.log"
    setup_logging("dbgpt", logging_level=logging_level, logger_filename=logger_filename)

    start_http = _check_has_http_trigger(dags)
    if start_http:
        from fastapi import FastAPI

        app = FastAPI()
    else:
        app = None
    system_app = SystemApp(app)
    DAGVar.set_current_system_app(system_app)
    trigger_manager = DefaultTriggerManager()
    system_app.register_instance(trigger_manager)

    for dag in dags:
        if show_dag_graph:
            try:
                dag_graph_file = dag.visualize_dag()
                if dag_graph_file:
                    logger.info(f"Visualize DAG {str(dag)} to {dag_graph_file}")
            except Exception as e:
                logger.warning(
                    f"Visualize DAG {str(dag)} failed: {e}, if your system has no "
                    f"graphviz, you can install it by `pip install graphviz` or "
                    f"`sudo apt install graphviz`"
                )
        for trigger in dag.trigger_nodes:
            trigger_manager.register_trigger(trigger, system_app)
    trigger_manager.after_register()
    if start_http and trigger_manager.keep_running() and app:
        import uvicorn

        # Should keep running
        uvicorn.run(app, host=host, port=port)


def _check_has_http_trigger(dags: List[DAG]) -> bool:
    """Check whether has http trigger.

    Args:
        dags (List[DAG]): The dags.

    Returns:
        bool: Whether has http trigger.
    """
    for dag in dags:
        for trigger in dag.trigger_nodes:
            if isinstance(trigger, HttpTrigger):
                return True
    return False
