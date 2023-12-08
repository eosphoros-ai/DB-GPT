from abc import ABC, abstractmethod
from typing import Generic, AsyncIterator
from ..task.base import OUT, IN, TaskOutput, TaskContext
from ..dag.base import DAGContext
from .base import BaseOperator


class StreamifyAbsOperator(BaseOperator[OUT], ABC, Generic[IN, OUT]):
    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        output = await curr_task_ctx.task_input.parent_outputs[0].task_output.streamify(
            self.streamify
        )
        curr_task_ctx.set_task_output(output)
        return output

    @abstractmethod
    async def streamify(self, input_value: IN) -> AsyncIterator[OUT]:
        """Convert a value of IN to an AsyncIterator[OUT]

        Args:
            input_value (IN): The data of parent operator's output

        Example:

        .. code-block:: python

            class MyStreamOperator(StreamifyAbsOperator[int, int]):
                async def streamify(self, input_value: int) -> AsyncIterator[int]
                    for i in range(input_value):
                        yield i
        """


class UnstreamifyAbsOperator(BaseOperator[OUT], Generic[IN, OUT]):
    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        output = await curr_task_ctx.task_input.parent_outputs[
            0
        ].task_output.unstreamify(self.unstreamify)
        curr_task_ctx.set_task_output(output)
        return output

    @abstractmethod
    async def unstreamify(self, input_value: AsyncIterator[IN]) -> OUT:
        """Convert a value of AsyncIterator[IN] to an OUT.

        Args:
            input_value (AsyncIterator[IN])): The data of parent operator's output

        Example:

        .. code-block:: python

            class MyUnstreamOperator(UnstreamifyAbsOperator[int, int]):
                async def unstreamify(self, input_value: AsyncIterator[int]) -> int
                    value_cnt = 0
                    async for v in input_value:
                        value_cnt += 1
                    return value_cnt
        """


class TransformStreamAbsOperator(BaseOperator[OUT], Generic[IN, OUT]):
    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        output = await curr_task_ctx.task_input.parent_outputs[
            0
        ].task_output.transform_stream(self.transform_stream)
        curr_task_ctx.set_task_output(output)
        return output

    @abstractmethod
    async def transform_stream(
        self, input_value: AsyncIterator[IN]
    ) -> AsyncIterator[OUT]:
        """Transform an AsyncIterator[IN] to another AsyncIterator[OUT] using a given function.

        Args:
            input_value (AsyncIterator[IN])): The data of parent operator's output

        Example:

        .. code-block:: python

            class MyTransformStreamOperator(TransformStreamAbsOperator[int, int]):
                async def unstreamify(self, input_value: AsyncIterator[int]) -> AsyncIterator[int]
                    async for v in input_value:
                        yield v + 1
        """
