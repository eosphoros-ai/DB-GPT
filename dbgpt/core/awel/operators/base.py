"""Base classes for operators that can be executed within a workflow."""
import asyncio
import functools
from abc import ABC, ABCMeta, abstractmethod
from types import FunctionType
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Generic,
    Iterator,
    Optional,
    TypeVar,
    Union,
    cast,
)

from dbgpt.component import ComponentType, SystemApp
from dbgpt.util.executor_utils import (
    AsyncToSyncIterator,
    BlockingFunction,
    DefaultExecutorFactory,
    blocking_func_to_async,
)

from ..dag.base import DAG, DAGContext, DAGNode, DAGVar
from ..task.base import EMPTY_DATA, OUT, T, TaskOutput

F = TypeVar("F", bound=FunctionType)

CALL_DATA = Union[Dict[str, Any], Any]


class WorkflowRunner(ABC, Generic[T]):
    """Abstract base class representing a runner for executing workflows in a DAG.

    This class defines the interface for executing workflows within the DAG,
    handling the flow from one DAG node to another.
    """

    @abstractmethod
    async def execute_workflow(
        self,
        node: "BaseOperator",
        call_data: Optional[CALL_DATA] = None,
        streaming_call: bool = False,
        exist_dag_ctx: Optional[DAGContext] = None,
    ) -> DAGContext:
        """Execute the workflow starting from a given operator.

        Args:
            node (RunnableDAGNode): The starting node of the workflow to be executed.
            call_data (CALL_DATA): The data pass to root operator node.
            streaming_call (bool): Whether the call is a streaming call.
            exist_dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.
        Returns:
            DAGContext: The context after executing the workflow, containing the final
                state and data.
        """


default_runner: Optional[WorkflowRunner] = None


class BaseOperatorMeta(ABCMeta):
    """Metaclass of BaseOperator."""

    @classmethod
    def _apply_defaults(cls, func: F) -> F:
        # sig_cache = signature(func)
        @functools.wraps(func)
        def apply_defaults(self: "BaseOperator", *args: Any, **kwargs: Any) -> Any:
            dag: Optional[DAG] = kwargs.get("dag") or DAGVar.get_current_dag()
            task_id: Optional[str] = kwargs.get("task_id")
            system_app: Optional[SystemApp] = (
                kwargs.get("system_app") or DAGVar.get_current_system_app()
            )
            executor = kwargs.get("executor") or DAGVar.get_executor()
            if not executor:
                if system_app:
                    executor = system_app.get_component(
                        ComponentType.EXECUTOR_DEFAULT, DefaultExecutorFactory
                    ).create()  # type: ignore
                else:
                    executor = DefaultExecutorFactory().create()
                DAGVar.set_executor(executor)

            if not task_id and dag:
                task_id = dag._new_node_id()
            runner: Optional[WorkflowRunner] = kwargs.get("runner") or default_runner
            # print(f"self: {self}, kwargs dag: {kwargs.get('dag')}, kwargs: {kwargs}")
            # for arg in sig_cache.parameters:
            #     if arg not in kwargs:
            #         kwargs[arg] = default_args[arg]
            if not kwargs.get("dag"):
                kwargs["dag"] = dag
            if not kwargs.get("task_id"):
                kwargs["task_id"] = task_id
            if not kwargs.get("runner"):
                kwargs["runner"] = runner
            if not kwargs.get("system_app"):
                kwargs["system_app"] = system_app
            if not kwargs.get("executor"):
                kwargs["executor"] = executor
            real_obj = func(self, *args, **kwargs)
            return real_obj

        return cast(F, apply_defaults)

    def __new__(cls, name, bases, namespace, **kwargs):
        """Create a new BaseOperator class with default arguments."""
        new_cls = super().__new__(cls, name, bases, namespace, **kwargs)
        new_cls.__init__ = cls._apply_defaults(new_cls.__init__)
        new_cls.after_define()
        return new_cls


class BaseOperator(DAGNode, ABC, Generic[OUT], metaclass=BaseOperatorMeta):
    """Abstract base class for operator nodes that can be executed within a workflow.

    This class extends DAGNode by adding execution capabilities.
    """

    streaming_operator: bool = False

    def __init__(
        self,
        task_id: Optional[str] = None,
        task_name: Optional[str] = None,
        dag: Optional[DAG] = None,
        runner: Optional[WorkflowRunner] = None,
        **kwargs,
    ) -> None:
        """Create a BaseOperator with an optional workflow runner.

        Args:
            runner (WorkflowRunner, optional): The runner used to execute the workflow.
                Defaults to None.
        """
        super().__init__(node_id=task_id, node_name=task_name, dag=dag, **kwargs)
        if not runner:
            from dbgpt.core.awel import DefaultWorkflowRunner

            runner = DefaultWorkflowRunner()

        self._runner: WorkflowRunner = runner
        self._dag_ctx: Optional[DAGContext] = None

    @property
    def current_dag_context(self) -> DAGContext:
        """Return the current DAG context."""
        if not self._dag_ctx:
            raise ValueError("DAGContext is not set")
        return self._dag_ctx

    @property
    def dev_mode(self) -> bool:
        """Whether the operator is in dev mode.

        In production mode, the default runner is not None.

        Returns:
            bool: Whether the operator is in dev mode. True if the
                default runner is None.
        """
        return default_runner is None

    async def _run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        if not self.node_id:
            raise ValueError(f"The DAG Node ID can't be empty, current node {self}")
        self._dag_ctx = dag_ctx
        return await self._do_run(dag_ctx)

    @abstractmethod
    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        """
        Abstract method to run the task within the DAG node.

        Args:
            dag_ctx (DAGContext): The context of the DAG when this node is run.

        Returns:
            TaskOutput[OUT]: The task output after this node has been run.
        """

    async def call(
        self,
        call_data: Optional[CALL_DATA] = EMPTY_DATA,
        dag_ctx: Optional[DAGContext] = None,
    ) -> OUT:
        """Execute the node and return the output.

        This method is a high-level wrapper for executing the node.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.
            dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.
        Returns:
            OUT: The output of the node after execution.
        """
        if call_data != EMPTY_DATA:
            call_data = {"data": call_data}
        out_ctx = await self._runner.execute_workflow(
            self, call_data, exist_dag_ctx=dag_ctx
        )
        return out_ctx.current_task_context.task_output.output

    def _blocking_call(
        self,
        call_data: Optional[CALL_DATA] = EMPTY_DATA,
        loop: Optional[asyncio.BaseEventLoop] = None,
    ) -> OUT:
        """Execute the node and return the output.

        This method is a high-level wrapper for executing the node.
        This method just for debug. Please use `call` method instead.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.

        Returns:
            OUT: The output of the node after execution.
        """
        from dbgpt.util.utils import get_or_create_event_loop

        if not loop:
            loop = get_or_create_event_loop()
        loop = cast(asyncio.BaseEventLoop, loop)
        return loop.run_until_complete(self.call(call_data))

    async def call_stream(
        self,
        call_data: Optional[CALL_DATA] = EMPTY_DATA,
        dag_ctx: Optional[DAGContext] = None,
    ) -> AsyncIterator[OUT]:
        """Execute the node and return the output as a stream.

        This method is used for nodes where the output is a stream.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.
            dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.

        Returns:
            AsyncIterator[OUT]: An asynchronous iterator over the output stream.
        """
        if call_data != EMPTY_DATA:
            call_data = {"data": call_data}
        out_ctx = await self._runner.execute_workflow(
            self, call_data, streaming_call=True, exist_dag_ctx=dag_ctx
        )
        return out_ctx.current_task_context.task_output.output_stream

    def _blocking_call_stream(
        self,
        call_data: Optional[CALL_DATA] = EMPTY_DATA,
        loop: Optional[asyncio.BaseEventLoop] = None,
    ) -> Iterator[OUT]:
        """Execute the node and return the output as a stream.

        This method is used for nodes where the output is a stream.
        This method just for debug. Please use `call_stream` method instead.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.

        Returns:
            Iterator[OUT]: An iterator over the output stream.
        """
        from dbgpt.util.utils import get_or_create_event_loop

        if not loop:
            loop = get_or_create_event_loop()
        return AsyncToSyncIterator(self.call_stream(call_data), loop)

    async def blocking_func_to_async(
        self, func: BlockingFunction, *args, **kwargs
    ) -> Any:
        """Execute a blocking function asynchronously.

        In AWEL, the operators are executed asynchronously. However,
        some functions are blocking, we run them in a separate thread.

        Args:
            func (BlockingFunction): The blocking function to be executed.
            *args: Positional arguments for the function.
            **kwargs: Keyword arguments for the function.
        """
        if not self._executor:
            raise ValueError("Executor is not set")
        return await blocking_func_to_async(self._executor, func, *args, **kwargs)


def initialize_runner(runner: WorkflowRunner):
    """Initialize the default runner."""
    global default_runner
    default_runner = runner
