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

from .dag.base import DAG, DAGContext
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
from .task.base import InputContext, InputSource, TaskContext, TaskOutput, TaskState
from .task.task_impl import (
    DefaultInputContext,
    DefaultTaskContext,
    SimpleCallDataInputSource,
    SimpleInputSource,
    SimpleStreamTaskOutput,
    SimpleTaskOutput,
    _is_async_iterator,
)
from .trigger.http_trigger import HttpTrigger

logger = logging.getLogger(__name__)

__all__ = [
    "initialize_awel",
    "DAGContext",
    "DAG",
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
    "TaskOutput",
    "TaskContext",
    "InputContext",
    "InputSource",
    "DefaultWorkflowRunner",
    "SimpleInputSource",
    "SimpleCallDataInputSource",
    "DefaultTaskContext",
    "DefaultInputContext",
    "SimpleTaskOutput",
    "SimpleStreamTaskOutput",
    "StreamifyAbsOperator",
    "UnstreamifyAbsOperator",
    "TransformStreamAbsOperator",
    "HttpTrigger",
    "setup_dev_environment",
    "_is_async_iterator",
]


def initialize_awel(system_app: SystemApp, dag_dirs: List[str]):
    """Initialize AWEL."""
    from .dag.base import DAGVar
    from .dag.dag_manager import DAGManager
    from .operators.base import initialize_runner
    from .trigger.trigger_manager import DefaultTriggerManager

    DAGVar.set_current_system_app(system_app)

    system_app.register(DefaultTriggerManager)
    dag_manager = DAGManager(system_app, dag_dirs)
    system_app.register_instance(dag_manager)
    initialize_runner(DefaultWorkflowRunner())
    # Load all dags
    dag_manager.load_dags()


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
    import uvicorn
    from fastapi import FastAPI

    from dbgpt.component import SystemApp
    from dbgpt.util.utils import setup_logging

    from .dag.base import DAGVar
    from .trigger.trigger_manager import DefaultTriggerManager

    if not logger_filename:
        logger_filename = "dbgpt_awel_dev.log"
    setup_logging("dbgpt", logging_level=logging_level, logger_filename=logger_filename)

    app = FastAPI()
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
            trigger_manager.register_trigger(trigger)
    trigger_manager.after_register()
    if trigger_manager.keep_running():
        # Should keep running
        uvicorn.run(app, host=host, port=port)
