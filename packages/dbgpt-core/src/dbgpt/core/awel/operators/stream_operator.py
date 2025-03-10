"""The module of stream operator."""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Generic

from ..dag.base import DAGContext
from ..task.base import IN, OUT, TaskContext, TaskOutput
from .base import BaseOperator


class StreamifyAbsOperator(BaseOperator[OUT], ABC, Generic[IN, OUT]):
    """An abstract operator that converts a value of IN to an AsyncIterator[OUT]."""

    streaming_operator = True

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        call_data = curr_task_ctx.call_data
        if call_data:
            wrapped_call_data = await curr_task_ctx._call_data_to_output()
            if not wrapped_call_data:
                raise ValueError(
                    f"task {curr_task_ctx.task_id} MapDAGNode expects wrapped_call_data"
                )
            output = await wrapped_call_data.streamify(self.streamify)
            curr_task_ctx.set_task_output(output)
            return output
        output = await curr_task_ctx.task_input.parent_outputs[0].task_output.streamify(
            self.streamify
        )
        curr_task_ctx.set_task_output(output)
        return output

    @abstractmethod
    async def streamify(self, input_value: IN) -> AsyncIterator[OUT]:
        """Convert a value of IN to an AsyncIterator[OUT].

        Args:
            input_value (IN): The data of parent operator's output

        Examples:
            .. code-block:: python

                class MyStreamOperator(StreamifyAbsOperator[int, int]):
                    async def streamify(self, input_value: int) -> AsyncIterator[int]:
                        for i in range(input_value):
                            yield i

        """


class UnstreamifyAbsOperator(BaseOperator[OUT], Generic[IN, OUT]):
    """An abstract operator that converts a value of AsyncIterator[IN] to an OUT."""

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        output: TaskOutput[OUT] = await curr_task_ctx.task_input.parent_outputs[
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
                    async def unstreamify(self, input_value: AsyncIterator[int]) -> int:
                        value_cnt = 0
                        async for v in input_value:
                            value_cnt += 1
                        return value_cnt
        """


class TransformStreamAbsOperator(BaseOperator[OUT], Generic[IN, OUT]):
    """Streaming to other streaming data.

    An abstract operator that transforms a value of
    AsyncIterator[IN] to another AsyncIterator[OUT].
    """

    streaming_operator = True

    async def _do_run(self, dag_ctx: DAGContext) -> TaskOutput[OUT]:
        curr_task_ctx: TaskContext[OUT] = dag_ctx.current_task_context
        output: TaskOutput[OUT] = await curr_task_ctx.task_input.parent_outputs[
            0
        ].task_output.transform_stream(self.transform_stream)

        curr_task_ctx.set_task_output(output)
        return output

    @abstractmethod
    async def transform_stream(
        self, input_value: AsyncIterator[IN]
    ) -> AsyncIterator[OUT]:
        """Transform an AsyncIterator[IN] to another AsyncIterator[OUT].

        Args:
            input_value (AsyncIterator[IN])): The data of parent operator's output

        Examples:
            .. code-block:: python

                class MyTransformStreamOperator(TransformStreamAbsOperator[int, int]):
                    async def unstreamify(
                        self, input_value: AsyncIterator[int]
                    ) -> AsyncIterator[int]:
                        async for v in input_value:
                            yield v + 1
        """
