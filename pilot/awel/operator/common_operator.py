from typing import Generic, Dict, List, Union, Callable, Any, AsyncIterator, Awaitable
import asyncio

from ..dag.base import DAGContext
from ..task.base import (
    TaskContext,
    TaskOutput,
    IN,
    OUT,
    InputContext,
    InputSource,
)

from .base import BaseOperator


class JoinOperator(BaseOperator, Generic[OUT]):
    """Operator that joins inputs using a custom combine function.

    This node type is useful for combining the outputs of upstream nodes.
    """

    def __init__(self, combine_function, **kwargs):
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
    def __init__(self, reduce_function=None, **kwargs):
        """Initializes a ReduceStreamOperator with a combine function.

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

    async def reduce(self, input_value: AsyncIterator[IN]) -> OUT:
        raise NotImplementedError


class MapOperator(BaseOperator, Generic[IN, OUT]):
    """Map operator that applies a mapping function to its inputs.

    This operator transforms its input data using a provided mapping function and
    passes the transformed data downstream.
    """

    def __init__(self, map_function=None, **kwargs):
        """Initializes a MapDAGNode with a mapping function.

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
        if not curr_task_ctx.task_input.check_single_parent():
            num_parents = len(curr_task_ctx.task_input.parent_outputs)
            raise ValueError(
                f"task {curr_task_ctx.task_id} MapDAGNode expects single parent, now number of parents: {num_parents}"
            )
        map_function = self.map_function or self.map

        input_ctx: InputContext = await curr_task_ctx.task_input.map(map_function)
        # All join result store in the first parent output
        reduce_output = input_ctx.parent_outputs[0].task_output
        curr_task_ctx.set_task_output(reduce_output)
        return reduce_output

    async def map(self, input_value: IN) -> OUT:
        raise NotImplementedError


BranchFunc = Union[Callable[[Any], bool], Callable[[Any], Awaitable[bool]]]


class BranchOperator(BaseOperator, Generic[OUT]):
    """Operator node that branches the workflow based on a provided function.

    This node filters its input data using a branching function and
    allows for conditional paths in the workflow.
    """

    def __init__(self, branches: Dict[BranchFunc, BaseOperator], **kwargs):
        """
        Initializes a BranchDAGNode with a branching function.

        Args:
            branches (Dict[BranchFunc, RunnableDAGNode]): Dict of function that defines the branching condition.

        Raises:
            ValueError: If the branch_function is not callable.
        """
        super().__init__(**kwargs)
        for branch_function in branches.keys():
            if not callable(branch_function):
                raise ValueError("branch_function must be callable")
        self.branches = branches

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

        branch_func_tasks = []
        branch_nodes: List[BaseOperator] = []
        for func, node in self.branches.items():
            branch_nodes.append(node)
            branch_func_tasks.append(
                curr_task_ctx.task_input.predicate_map(func, failed_value=None)
            )
        branch_input_ctxs: List[InputContext] = await asyncio.gather(*branch_func_tasks)
        parent_output = task_input.parent_outputs[0].task_output
        curr_task_ctx.set_task_output(parent_output)

        for i, ctx in enumerate(branch_input_ctxs):
            node = branch_nodes[i]
            if ctx.parent_outputs[0].task_output.is_empty:
                # Skip current node
                # node.current_task_context.set_current_state(TaskState.SKIP)
                pass
            else:
                pass
        raise NotImplementedError
        return None


class InputOperator(BaseOperator, Generic[OUT]):
    def __init__(self, input_source: InputSource[OUT], **kwargs) -> None:
        super().__init__(**kwargs)
        self._input_source = input_source

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        task_output = await self._input_source.read(curr_task_ctx)
        curr_task_ctx.set_task_output(task_output)
        return task_output
