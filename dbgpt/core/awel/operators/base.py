"""Base classes for operators that can be executed within a workflow."""

import asyncio
import functools
import logging
from abc import ABC, ABCMeta, abstractmethod
from contextvars import ContextVar
from types import FunctionType
from typing import (
    TYPE_CHECKING,
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
from dbgpt.configs import VARIABLES_SCOPE_FLOW_PRIVATE
from dbgpt.util.executor_utils import (
    AsyncToSyncIterator,
    BlockingFunction,
    DefaultExecutorFactory,
    blocking_func_to_async,
)
from dbgpt.util.tracer import root_tracer

from ..dag.base import DAG, DAGContext, DAGNode, DAGVar, DAGVariables
from ..task.base import EMPTY_DATA, OUT, T, TaskOutput, is_empty_data

if TYPE_CHECKING:
    from ...interface.variables import VariablesProvider

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=FunctionType)

CALL_DATA = Union[Dict[str, Any], Any]
CURRENT_DAG_CONTEXT: ContextVar[Optional[DAGContext]] = ContextVar(
    "current_dag_context", default=None
)


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
        dag_variables: Optional[DAGVariables] = None,
    ) -> DAGContext:
        """Execute the workflow starting from a given operator.

        Args:
            node (RunnableDAGNode): The starting node of the workflow to be executed.
            call_data (CALL_DATA): The data pass to root operator node.
            streaming_call (bool): Whether the call is a streaming call.
            exist_dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.
            dag_variables (DAGVariables): The DAG variables.
        Returns:
            DAGContext: The context after executing the workflow, containing the final
                state and data.
        """


default_runner: Optional[WorkflowRunner] = None


def _dev_mode() -> bool:
    """Check if the operator is in dev mode.

    In production mode, the default runner is not None, and the operator will run in
    the same process with the DB-GPT webserver.
    """
    return default_runner is None


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
            variables_provider = (
                kwargs.get("variables_provider") or DAGVar.get_variables_provider()
            )
            if not executor:
                if system_app:
                    executor = system_app.get_component(
                        ComponentType.EXECUTOR_DEFAULT,
                        DefaultExecutorFactory,
                        default_component=DefaultExecutorFactory(),
                    ).create()  # type: ignore
                else:
                    executor = DefaultExecutorFactory().create()
                DAGVar.set_executor(executor)
            if not variables_provider:
                from ...interface.variables import VariablesProvider

                if system_app:
                    variables_provider = system_app.get_component(
                        ComponentType.VARIABLES_PROVIDER,
                        VariablesProvider,
                        default_component=None,
                    )
                else:
                    from ...interface.variables import StorageVariablesProvider

                    variables_provider = StorageVariablesProvider()
                DAGVar.set_variables_provider(variables_provider)

            if not task_id and dag:
                task_id = dag._new_node_id()
            runner: Optional[WorkflowRunner] = kwargs.get("runner") or default_runner
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
            if not kwargs.get("variables_provider"):
                kwargs["variables_provider"] = variables_provider
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
    incremental_output: bool = False
    output_format: Optional[str] = None

    def __init__(
        self,
        task_id: Optional[str] = None,
        task_name: Optional[str] = None,
        dag: Optional[DAG] = None,
        runner: Optional[WorkflowRunner] = None,
        can_skip_in_branch: bool = True,
        variables_provider: Optional["VariablesProvider"] = None,
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
        if "incremental_output" in kwargs:
            self.incremental_output = bool(kwargs["incremental_output"])
        if "output_format" in kwargs:
            self.output_format = kwargs["output_format"]
        self._runner: WorkflowRunner = runner
        self._dag_ctx: Optional[DAGContext] = None
        self._can_skip_in_branch = can_skip_in_branch
        self._variables_provider = variables_provider

    def __getstate__(self):
        """Customize the pickling process."""
        state = self.__dict__.copy()
        if "_runner" in state:
            del state["_runner"]
        if "_executor" in state:
            del state["_executor"]
        if "_system_app" in state:
            del state["_system_app"]
        return state

    def __setstate__(self, state):
        """Customize the unpickling process."""
        self.__dict__.update(state)
        self._runner = default_runner
        self._system_app = DAGVar.get_current_system_app()
        self._executor = DAGVar.get_executor()

    @property
    def current_dag_context(self) -> DAGContext:
        """Return the current DAG context."""
        ctx = CURRENT_DAG_CONTEXT.get()
        if not ctx:
            raise ValueError("DAGContext is not set")
        return ctx

    @property
    def dev_mode(self) -> bool:
        """Whether the operator is in dev mode.

        In production mode, the default runner is not None, and the operator will run in
        the same process with the DB-GPT webserver.

        Returns:
            bool: Whether the operator is in dev mode. True if the
                default runner is None.
        """
        return _dev_mode()

    async def _run(self, dag_ctx: DAGContext, task_log_id: str) -> TaskOutput[OUT]:
        if not self.node_id:
            raise ValueError(f"The DAG Node ID can't be empty, current node {self}")
        if not task_log_id:
            raise ValueError(f"The task log ID can't be empty, current node {self}")
        CURRENT_DAG_CONTEXT.set(dag_ctx)
        # Resolve variables
        await self._resolve_variables(dag_ctx)
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
        dag_variables: Optional[DAGVariables] = None,
    ) -> OUT:
        """Execute the node and return the output.

        This method is a high-level wrapper for executing the node.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.
            dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.
            dag_variables (DAGVariables): The DAG variables passed to current DAG.
        Returns:
            OUT: The output of the node after execution.
        """
        if not is_empty_data(call_data):
            call_data = {"data": call_data}
        with root_tracer.start_span("dbgpt.awel.operator.call"):
            out_ctx = await self._runner.execute_workflow(
                self, call_data, exist_dag_ctx=dag_ctx, dag_variables=dag_variables
            )
            return out_ctx.current_task_context.task_output.output

    def _blocking_call(
        self,
        call_data: Optional[CALL_DATA] = EMPTY_DATA,
        dag_ctx: Optional[DAGContext] = None,
        dag_variables: Optional[DAGVariables] = None,
        loop: Optional[asyncio.BaseEventLoop] = None,
    ) -> OUT:
        """Execute the node and return the output.

        This method is a high-level wrapper for executing the node.
        This method just for debug. Please use `call` method instead.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.
            dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.
            dag_variables (DAGVariables): The DAG variables passed to current DAG.
            loop (asyncio.BaseEventLoop): The event loop to run the operator.
        Returns:
            OUT: The output of the node after execution.
        """
        from dbgpt.util.utils import get_or_create_event_loop

        if not loop:
            loop = get_or_create_event_loop()
        loop = cast(asyncio.BaseEventLoop, loop)
        return loop.run_until_complete(self.call(call_data, dag_ctx, dag_variables))

    async def call_stream(
        self,
        call_data: Optional[CALL_DATA] = EMPTY_DATA,
        dag_ctx: Optional[DAGContext] = None,
        dag_variables: Optional[DAGVariables] = None,
    ) -> AsyncIterator[OUT]:
        """Execute the node and return the output as a stream.

        This method is used for nodes where the output is a stream.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.
            dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.
            dag_variables (DAGVariables): The DAG variables passed to current DAG.
        Returns:
            AsyncIterator[OUT]: An asynchronous iterator over the output stream.
        """
        if call_data != EMPTY_DATA:
            call_data = {"data": call_data}
        with root_tracer.start_span("dbgpt.awel.operator.call_stream"):
            out_ctx = await self._runner.execute_workflow(
                self,
                call_data,
                streaming_call=True,
                exist_dag_ctx=dag_ctx,
                dag_variables=dag_variables,
            )

            task_output = out_ctx.current_task_context.task_output
            if task_output.is_stream:
                stream_generator = (
                    out_ctx.current_task_context.task_output.output_stream
                )
            else:
                # No stream output, wrap the output in a stream
                async def _gen():
                    yield task_output.output

                stream_generator = _gen()
            return root_tracer.wrapper_async_stream(
                stream_generator, "dbgpt.awel.operator.call_stream.iterate"
            )

    def _blocking_call_stream(
        self,
        call_data: Optional[CALL_DATA] = EMPTY_DATA,
        dag_ctx: Optional[DAGContext] = None,
        dag_variables: Optional[DAGVariables] = None,
        loop: Optional[asyncio.BaseEventLoop] = None,
    ) -> Iterator[OUT]:
        """Execute the node and return the output as a stream.

        This method is used for nodes where the output is a stream.
        This method just for debug. Please use `call_stream` method instead.

        Args:
            call_data (CALL_DATA): The data pass to root operator node.
            dag_ctx (DAGContext): The context of the DAG when this node is run,
                Defaults to None.
            dag_variables (DAGVariables): The DAG variables passed to current DAG.
            loop (asyncio.BaseEventLoop): The event loop to run the operator.
        Returns:
            Iterator[OUT]: An iterator over the output stream.
        """
        from dbgpt.util.utils import get_or_create_event_loop

        if not loop:
            loop = get_or_create_event_loop()
        return AsyncToSyncIterator(
            self.call_stream(call_data, dag_ctx, dag_variables), loop
        )

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

    @property
    def current_event_loop_task_id(self) -> int:
        """Get the current event loop task id."""
        return id(asyncio.current_task())

    def can_skip_in_branch(self) -> bool:
        """Check if the operator can be skipped in the branch."""
        return self._can_skip_in_branch

    async def _resolve_variables(self, dag_ctx: DAGContext):
        """Resolve variables in the operator.

        Some attributes of the operator may be VariablesPlaceHolder, which need to be
        resolved before the operator is executed.

        Args:
            dag_ctx (DAGContext): The context of the DAG when this node is run.
        """
        from ...interface.variables import (
            VariablesIdentifier,
            VariablesPlaceHolder,
            is_variable_string,
        )

        if not self._variables_provider:
            return

        if dag_ctx._dag_variables:
            # Resolve variables in DAG context
            resolve_tasks = []
            resolve_items = []
            for item in dag_ctx._dag_variables.items:
                # TODO: Resolve variables just once?
                if not item.value:
                    continue
                if isinstance(item.value, str) and is_variable_string(item.value):
                    item.value = VariablesPlaceHolder(item.name, item.value)
                if isinstance(item.value, VariablesPlaceHolder):
                    resolve_tasks.append(
                        item.value.async_parse(self._variables_provider)
                    )
                    resolve_items.append(item)
            resolved_values = await asyncio.gather(*resolve_tasks)
            for item, rv in zip(resolve_items, resolved_values):
                item.value = rv
        dag_provider: Optional["VariablesProvider"] = None
        if dag_ctx._dag_variables:
            dag_provider = dag_ctx._dag_variables.to_provider()

        # TODO: Resolve variables parallel
        for attr, value in self.__dict__.items():
            # Handle all attributes that are VariablesPlaceHolder
            if isinstance(value, VariablesPlaceHolder):
                resolved_value: Any = None
                default_identifier_map = None
                id_key = VariablesIdentifier.from_str_identifier(value.full_key)
                if (
                    id_key.scope == VARIABLES_SCOPE_FLOW_PRIVATE
                    and id_key.scope_key is None
                    and self.dag
                ):
                    default_identifier_map = {"scope_key": self.dag.dag_id}

                if dag_provider:
                    # First try to resolve the variable with the DAG variables
                    resolved_value = await value.async_parse(
                        dag_provider,
                        ignore_not_found_error=True,
                        default_identifier_map=default_identifier_map,
                    )
                if resolved_value is None:
                    resolved_value = await value.async_parse(
                        self._variables_provider,
                        default_identifier_map=default_identifier_map,
                    )
                    logger.debug(
                        f"Resolve variable {attr} with value {resolved_value} for "
                        f"{self} from system variables"
                    )
                else:
                    logger.debug(
                        f"Resolve variable {attr} with value {resolved_value} for "
                        f"{self} from DAG variables"
                    )
                setattr(self, attr, resolved_value)


def initialize_runner(runner: WorkflowRunner):
    """Initialize the default runner."""
    global default_runner
    default_runner = runner
