"""Agentic Workflow Expression Language (AWEL)

Note:

AWEL is still an experimental feature and only opens the lowest level API. 
The stability of this API cannot be guaranteed at present.

"""

from typing import List, Optional

from dbgpt.component import SystemApp

from .dag.base import DAG, DAGContext
from .operator.base import BaseOperator, WorkflowRunner
from .operator.common_operator import (
    BranchFunc,
    BranchOperator,
    InputOperator,
    JoinOperator,
    MapOperator,
    ReduceStreamOperator,
)
from .operator.stream_operator import (
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

__all__ = [
    "initialize_awel",
    "DAGContext",
    "DAG",
    "BaseOperator",
    "JoinOperator",
    "ReduceStreamOperator",
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
]


def initialize_awel(system_app: SystemApp, dag_dirs: List[str]):
    from .dag.base import DAGVar
    from .dag.dag_manager import DAGManager
    from .operator.base import initialize_runner
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
    host: Optional[str] = "0.0.0.0",
    port: Optional[int] = 5555,
    logging_level: Optional[str] = None,
    logger_filename: Optional[str] = None,
) -> None:
    """Setup a development environment for AWEL.

    Just using in development environment, not production environment.
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
        for trigger in dag.trigger_nodes:
            trigger_manager.register_trigger(trigger)
    trigger_manager.after_register()
    uvicorn.run(app, host=host, port=port)
