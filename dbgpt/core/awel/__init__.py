"""Agentic Workflow Expression Language (AWEL)

Note:

AWEL is still an experimental feature and only opens the lowest level API. 
The stability of this API cannot be guaranteed at present.

"""

from dbgpt.component import SystemApp

from .dag.base import DAGContext, DAG

from .operator.base import BaseOperator, WorkflowRunner
from .operator.common_operator import (
    JoinOperator,
    ReduceStreamOperator,
    MapOperator,
    BranchOperator,
    InputOperator,
    BranchFunc,
)

from .operator.stream_operator import (
    StreamifyAbsOperator,
    UnstreamifyAbsOperator,
    TransformStreamAbsOperator,
)

from .task.base import TaskState, TaskOutput, TaskContext, InputContext, InputSource
from .task.task_impl import (
    SimpleInputSource,
    SimpleCallDataInputSource,
    DefaultTaskContext,
    DefaultInputContext,
    SimpleTaskOutput,
    SimpleStreamTaskOutput,
    _is_async_iterator,
)
from .trigger.http_trigger import HttpTrigger
from .runner.local_runner import DefaultWorkflowRunner

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
]


def initialize_awel(system_app: SystemApp, dag_filepath: str):
    from .dag.dag_manager import DAGManager
    from .dag.base import DAGVar
    from .trigger.trigger_manager import DefaultTriggerManager
    from .operator.base import initialize_runner

    DAGVar.set_current_system_app(system_app)

    system_app.register(DefaultTriggerManager)
    dag_manager = DAGManager(system_app, dag_filepath)
    system_app.register_instance(dag_manager)
    initialize_runner(DefaultWorkflowRunner())
    # Load all dags
    dag_manager.load_dags()
