"""The Abstract Retriever Operator."""
from abc import abstractmethod

from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.task.base import IN, OUT


class RetrieverOperator(MapOperator[IN, OUT]):
    """The Abstract Retriever Operator."""

    async def map(self, input_value: IN) -> OUT:
        """Map input value to output value.

        Args:
            input_value (IN): The input value.

        Returns:
            OUT: The output value.
        """
        # The retrieve function is blocking, so we need to wrap it in a
        # blocking_func_to_async.
        return await self.blocking_func_to_async(self.retrieve, input_value)

    @abstractmethod
    def retrieve(self, input_value: IN) -> OUT:
        """Retrieve data for input value."""
