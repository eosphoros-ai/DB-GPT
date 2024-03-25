"""Common operators of AWEL."""
import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Union

from ..dag.base import DAGContext
from ..task.base import (
    IN,
    OUT,
    SKIP_DATA,
    InputContext,
    InputSource,
    JoinFunc,
    MapFunc,
    ReduceFunc,
    TaskContext,
    TaskOutput,
)
from .base import BaseOperator

logger = logging.getLogger(__name__)


class JoinOperator(BaseOperator, Generic[OUT]):
    """Operator that joins inputs using a custom combine function.

    This node type is useful for combining the outputs of upstream nodes.
    """

    def __init__(self, combine_function: JoinFunc, **kwargs):
        """Create a JoinDAGNode with a combine function.

        Args:
            combine_function: A function that defines how to combine inputs.
        """
        super().__init__(**kwargs)
        if not callable(combine_function):
            raise ValueError("combine_function must be callable")
        self.combine_function = combine_function

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        """Run the join operation on the DAG context's inputs.

        Args:
            dag_ctx (DAGContext): The current context of the DAG.

        Returns:
            TaskOutput[OUT]: The task output after this node has been run.
        """
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        input_ctx: InputContext = await curr_task_ctx.task_input.map_all(
            self.combine_function
        )
        # All join result store in the first parent output
        join_output = input_ctx.parent_outputs[0].task_output
        curr_task_ctx.set_task_output(join_output)
        return join_output


class ReduceStreamOperator(BaseOperator, Generic[IN, OUT]):
    """Operator that reduces inputs using a custom reduce function."""

    def __init__(self, reduce_function: Optional[ReduceFunc] = None, **kwargs):
        """Create a ReduceStreamOperator with a combine function.

        Args:
            combine_function: A function that defines how to combine inputs.

        Raises:
            ValueError: If the combine_function is not callable.
        """
        super().__init__(**kwargs)
        if reduce_function and not callable(reduce_function):
            raise ValueError("reduce_function must be callable")
        self.reduce_function = reduce_function

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        """Run the join operation on the DAG context's inputs.

        Args:
            dag_ctx (DAGContext): The current context of the DAG.

        Returns:
            TaskOutput[OUT]: The task output after this node has been run.
        """
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        task_input = curr_task_ctx.task_input
        if not task_input.check_stream():
            raise ValueError("ReduceStreamOperator expects stream data")
        if not task_input.check_single_parent():
            raise ValueError("ReduceStreamOperator expects single parent")

        reduce_function = self.reduce_function or self.reduce

        input_ctx: InputContext = await task_input.reduce(reduce_function)
        # All join result store in the first parent output
        reduce_output = input_ctx.parent_outputs[0].task_output
        curr_task_ctx.set_task_output(reduce_output)
        return reduce_output

    async def reduce(self, a: IN, b: IN) -> OUT:
        """Reduce the input stream to a single value."""
        raise NotImplementedError


class MapOperator(BaseOperator, Generic[IN, OUT]):
    """Map operator that applies a mapping function to its inputs.

    This operator transforms its input data using a provided mapping function and
    passes the transformed data downstream.
    """

    def __init__(self, map_function: Optional[MapFunc] = None, **kwargs):
        """Create a MapDAGNode with a mapping function.

        Args:
            map_function: A function that defines how to map the input data.

        Raises:
            ValueError: If the map_function is not callable.
        """
        super().__init__(**kwargs)
        if map_function and not callable(map_function):
            raise ValueError("map_function must be callable")
        self.map_function = map_function

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        """Run the mapping operation on the DAG context's inputs.

        This method applies the mapping function to the input context and updates
        the DAG context with the new data.

        Args:
            dag_ctx (DAGContext[IN]): The current context of the DAG.

        Returns:
            TaskOutput[OUT]: The task output after this node has been run.

        Raises:
            ValueError: If not a single parent or the map_function is not callable
        """
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        call_data = curr_task_ctx.call_data
        if not call_data and not curr_task_ctx.task_input.check_single_parent():
            num_parents = len(curr_task_ctx.task_input.parent_outputs)
            raise ValueError(
                f"task {curr_task_ctx.task_id} MapDAGNode expects single parent,"
                f"now number of parents: {num_parents}"
            )
        map_function = self.map_function or self.map

        if call_data:
            wrapped_call_data = await curr_task_ctx._call_data_to_output()
            if not wrapped_call_data:
                raise ValueError(
                    f"task {curr_task_ctx.task_id} MapDAGNode expects wrapped_call_data"
                )
            output: TaskOutput[OUT] = await wrapped_call_data.map(map_function)
            curr_task_ctx.set_task_output(output)
            return output

        input_ctx: InputContext = await curr_task_ctx.task_input.map(map_function)
        # All join result store in the first parent output
        output = input_ctx.parent_outputs[0].task_output
        curr_task_ctx.set_task_output(output)
        return output

    async def map(self, input_value: IN) -> OUT:
        """Map the input data to a new value."""
        raise NotImplementedError


BranchFunc = Union[Callable[[IN], bool], Callable[[IN], Awaitable[bool]]]


class BranchOperator(BaseOperator, Generic[IN, OUT]):
    """Operator node that branches the workflow based on a provided function.

    This node filters its input data using a branching function and
    allows for conditional paths in the workflow.

    If a branch function returns True, the corresponding task will be executed.
    otherwise, the corresponding task will be skipped, and the output of
    this skip node will be set to `SKIP_DATA`

    """

    def __init__(
        self,
        branches: Optional[Dict[BranchFunc[IN], Union[BaseOperator, str]]] = None,
        **kwargs,
    ):
        """Create a BranchDAGNode with a branching function.

        Args:
            branches (Dict[BranchFunc[IN], Union[BaseOperator, str]]):
                Dict of function that defines the branching condition.

        Raises:
            ValueError: If the branch_function is not callable.
        """
        super().__init__(**kwargs)
        if branches:
            for branch_function, value in branches.items():
                if not callable(branch_function):
                    raise ValueError("branch_function must be callable")
                if isinstance(value, BaseOperator):
                    if not value.node_name:
                        raise ValueError("branch node name must be set")
                    branches[branch_function] = value.node_name
        self._branches = branches

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        """Run the branching operation on the DAG context's inputs.

        This method applies the branching function to the input context to determine
        the path of execution in the workflow.

        Args:
            dag_ctx (DAGContext[IN]): The current context of the DAG.

        Returns:
            TaskOutput[OUT]: The task output after this node has been run.
        """
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        task_input = curr_task_ctx.task_input
        if task_input.check_stream():
            raise ValueError("BranchDAGNode expects no stream data")
        if not task_input.check_single_parent():
            raise ValueError("BranchDAGNode expects single parent")

        branches = self._branches
        if not branches:
            branches = await self.branches()

        branch_func_tasks = []
        branch_nodes: List[Union[BaseOperator, str]] = []
        for func, node_name in branches.items():
            branch_nodes.append(node_name)
            branch_func_tasks.append(
                curr_task_ctx.task_input.predicate_map(func, failed_value=None)
            )

        branch_input_ctxs: List[InputContext] = await asyncio.gather(*branch_func_tasks)
        parent_output = task_input.parent_outputs[0].task_output
        curr_task_ctx.set_task_output(parent_output)
        skip_node_names = []
        for i, ctx in enumerate(branch_input_ctxs):
            node_name = branch_nodes[i]
            branch_out = ctx.parent_outputs[0].task_output
            logger.info(
                f"branch_input_ctxs {i} result {branch_out.output}, "
                f"is_empty: {branch_out.is_empty}"
            )
            if ctx.parent_outputs[0].task_output.is_none:
                logger.info(f"Skip node name {node_name}")
                skip_node_names.append(node_name)
        curr_task_ctx.update_metadata("skip_node_names", skip_node_names)
        return parent_output

    async def branches(self) -> Dict[BranchFunc[IN], Union[BaseOperator, str]]:
        """Return branch logic based on input data."""
        raise NotImplementedError


class InputOperator(BaseOperator, Generic[OUT]):
    """Operator node that reads data from an input source."""

    def __init__(self, input_source: InputSource[OUT], **kwargs) -> None:
        """Create an InputDAGNode with an input source."""
        super().__init__(**kwargs)
        self._input_source = input_source

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        task_output = await self._input_source.read(curr_task_ctx)
        curr_task_ctx.set_task_output(task_output)
        return task_output

    @classmethod
    def dummy_input(cls, dummy_data: Any = SKIP_DATA, **kwargs) -> "InputOperator[OUT]":
        """Create a dummy InputOperator with a given input value."""
        return cls(input_source=InputSource.from_data(dummy_data), **kwargs)


class TriggerOperator(InputOperator[OUT], Generic[OUT]):
    """Operator node that triggers the DAG to run."""

    def __init__(self, **kwargs) -> None:
        """Create a TriggerDAGNode."""
        from ..task.task_impl import SimpleCallDataInputSource

        super().__init__(input_source=SimpleCallDataInputSource(), **kwargs)
