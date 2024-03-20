"""The default implementation of Task.

This implementation can run workflow in local machine.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import (
    Any,
    AsyncIterator,
    Callable,
    Coroutine,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

from .base import (
    _EMPTY_DATA_TYPE,
    EMPTY_DATA,
    OUT,
    PLACEHOLDER_DATA,
    InputContext,
    InputSource,
    MapFunc,
    PredicateFunc,
    ReduceFunc,
    StreamFunc,
    T,
    TaskContext,
    TaskOutput,
    TaskState,
    TransformFunc,
    UnStreamFunc,
    is_empty_data,
)

logger = logging.getLogger(__name__)


async def _reduce_stream(stream: AsyncIterator, reduce_function) -> Any:
    # Init accumulator
    try:
        accumulator = await stream.__anext__()
    except StopAsyncIteration:
        raise ValueError("Stream is empty")
    is_async = asyncio.iscoroutinefunction(reduce_function)
    async for element in stream:
        if is_async:
            accumulator = await reduce_function(accumulator, element)
        else:
            accumulator = reduce_function(accumulator, element)
    return accumulator


class SimpleTaskOutput(TaskOutput[T], Generic[T]):
    """The default implementation of TaskOutput.

    It wraps the no stream data and provide some basic data operations.
    """

    def __init__(self, data: Union[T, _EMPTY_DATA_TYPE] = EMPTY_DATA) -> None:
        """Create a SimpleTaskOutput.

        Args:
            data (Union[T, _EMPTY_DATA_TYPE], optional): The output data. Defaults to
                EMPTY_DATA.
        """
        super().__init__()
        self._data = data

    @property
    def output(self) -> T:
        """Return the output data."""
        if EMPTY_DATA.is_same(self._data):
            raise ValueError("No output data for current task output")
        return cast(T, self._data)

    def set_output(self, output_data: T | AsyncIterator[T]) -> None:
        """Save the output data to current object.

        Args:
            output_data (T | AsyncIterator[T]): The output data.
        """
        if _is_async_iterator(output_data):
            raise ValueError(
                f"Can not set stream data {output_data} to SimpleTaskOutput"
            )
        self._data = cast(T, output_data)

    def new_output(self) -> TaskOutput[T]:
        """Create new output object with empty data."""
        return SimpleTaskOutput()

    @property
    def is_empty(self) -> bool:
        """Return True if the output data is empty."""
        return is_empty_data(self._data)

    @property
    def is_none(self) -> bool:
        """Return True if the output data is None."""
        return self._data is None

    async def _apply_func(self, func) -> Any:
        """Apply the function to current output data."""
        if asyncio.iscoroutinefunction(func):
            out = await func(self._data)
        else:
            out = func(self._data)
        return out

    async def map(self, map_func: MapFunc) -> TaskOutput[OUT]:
        """Apply a mapping function to the task's output.

        Args:
            map_func (MapFunc): A function to apply to the task's output.

        Returns:
            TaskOutput[OUT]: The result of applying the mapping function.
        """
        out = await self._apply_func(map_func)
        return SimpleTaskOutput(out)

    async def check_condition(self, condition_func) -> TaskOutput[OUT]:
        """Check the condition function."""
        out = await self._apply_func(condition_func)
        if out:
            return SimpleTaskOutput(PLACEHOLDER_DATA)
        return SimpleTaskOutput(EMPTY_DATA)

    async def streamify(self, transform_func: StreamFunc) -> TaskOutput[OUT]:
        """Transform the task's output to a stream output.

        Args:
            transform_func (StreamFunc): A function to transform the task's output to a
                stream output.

        Returns:
            TaskOutput[OUT]: The result of transforming the task's output to a stream
                output.
        """
        out = await self._apply_func(transform_func)
        return SimpleStreamTaskOutput(out)


class SimpleStreamTaskOutput(TaskOutput[T], Generic[T]):
    """The default stream implementation of TaskOutput."""

    def __init__(
        self, data: Union[AsyncIterator[T], _EMPTY_DATA_TYPE] = EMPTY_DATA
    ) -> None:
        """Create a SimpleStreamTaskOutput.

        Args:
            data (Union[AsyncIterator[T], _EMPTY_DATA_TYPE], optional): The output data.
                Defaults to EMPTY_DATA.
        """
        super().__init__()
        self._data = data

    @property
    def is_stream(self) -> bool:
        """Return True if the output data is a stream."""
        return True

    @property
    def is_empty(self) -> bool:
        """Return True if the output data is empty."""
        return is_empty_data(self._data)

    @property
    def is_none(self) -> bool:
        """Return True if the output data is None."""
        return self._data is None

    @property
    def output_stream(self) -> AsyncIterator[T]:
        """Return the output data.

        Returns:
            AsyncIterator[T]: The output data.

        Raises:
            ValueError: If the output data is empty.
        """
        if EMPTY_DATA.is_same(self._data):
            raise ValueError("No output data for current task output")
        return cast(AsyncIterator[T], self._data)

    def set_output(self, output_data: T | AsyncIterator[T]) -> None:
        """Save the output data to current object.

        Raises:
            ValueError: If the output data is not a stream.
        """
        if not _is_async_iterator(output_data):
            raise ValueError(
                f"Can not set non-stream data {output_data} to SimpleStreamTaskOutput"
            )
        self._data = cast(AsyncIterator[T], output_data)

    def new_output(self) -> TaskOutput[T]:
        """Create new output object with empty data."""
        return SimpleStreamTaskOutput()

    async def map(self, map_func: MapFunc) -> TaskOutput[OUT]:
        """Apply a mapping function to the task's output."""
        is_async = asyncio.iscoroutinefunction(map_func)

        async def new_iter() -> AsyncIterator[OUT]:
            async for out in self.output_stream:
                if is_async:
                    new_out: OUT = await map_func(out)
                else:
                    new_out = cast(OUT, map_func(out))
                yield new_out

        return SimpleStreamTaskOutput(new_iter())

    async def reduce(self, reduce_func: ReduceFunc) -> TaskOutput[OUT]:
        """Apply a reduce function to the task's output."""
        out = await _reduce_stream(self.output_stream, reduce_func)
        return SimpleTaskOutput(out)

    async def unstreamify(self, transform_func: UnStreamFunc) -> TaskOutput[OUT]:
        """Transform the task's output to a non-stream output."""
        if asyncio.iscoroutinefunction(transform_func):
            out = await transform_func(self.output_stream)
        else:
            out = transform_func(self.output_stream)
        return SimpleTaskOutput(out)

    async def transform_stream(self, transform_func: TransformFunc) -> TaskOutput[OUT]:
        """Transform an AsyncIterator[T] to another AsyncIterator[T].

        Args:
            transform_func (Callable[[AsyncIterator[T]], AsyncIterator[T]]): Function to
                 apply to the AsyncIterator[T].

        Returns:
            TaskOutput[T]: The result of applying the reducing function.
        """
        if asyncio.iscoroutinefunction(transform_func):
            out: AsyncIterator[OUT] = await transform_func(self.output_stream)
        else:
            out = cast(AsyncIterator[OUT], transform_func(self.output_stream))
        return SimpleStreamTaskOutput(out)


def _is_async_iterator(obj):
    return (
        hasattr(obj, "__anext__")
        and callable(getattr(obj, "__anext__", None))
        and hasattr(obj, "__aiter__")
        and callable(getattr(obj, "__aiter__", None))
    )


def _is_async_iterable(obj):
    return hasattr(obj, "__aiter__") and callable(getattr(obj, "__aiter__", None))


def _is_iterator(obj):
    return (
        hasattr(obj, "__iter__")
        and callable(getattr(obj, "__iter__", None))
        and hasattr(obj, "__next__")
        and callable(getattr(obj, "__next__", None))
    )


def _is_iterable(obj):
    return hasattr(obj, "__iter__") and callable(getattr(obj, "__iter__", None))


async def _to_async_iterator(obj) -> AsyncIterator:
    if _is_async_iterable(obj):
        async for item in obj:
            yield item
    elif _is_iterable(obj):
        for item in obj:
            yield item
    else:
        raise ValueError(f"Can not convert {obj} to AsyncIterator")


class BaseInputSource(InputSource, ABC):
    """The base class of InputSource."""

    def __init__(self, streaming: Optional[bool] = None) -> None:
        """Create a BaseInputSource."""
        super().__init__()
        self._is_read = False
        self._streaming_data = streaming

    @abstractmethod
    def _read_data(self, task_ctx: TaskContext) -> Any:
        """Return data with task context."""

    async def read(self, task_ctx: TaskContext) -> TaskOutput:
        """Read data with task context.

        Args:
            task_ctx (TaskContext): The task context.

        Returns:
            TaskOutput: The task output.

        Raises:
            ValueError: If the input source is a stream and has been read.
        """
        data = self._read_data(task_ctx)
        if self._streaming_data is None:
            streaming_data = _is_async_iterator(data) or _is_iterator(data)
        else:
            streaming_data = self._streaming_data
        if streaming_data:
            if self._is_read:
                raise ValueError(f"Input iterator {data} has been read!")
            it_data = _to_async_iterator(data)
            output: TaskOutput = SimpleStreamTaskOutput(it_data)
        else:
            output = SimpleTaskOutput(data)
        self._is_read = True
        return output


class SimpleInputSource(BaseInputSource):
    """The default implementation of InputSource."""

    def __init__(self, data: Any, streaming: Optional[bool] = None) -> None:
        """Create a SimpleInputSource.

        Args:
            data (Any): The input data.
        """
        super().__init__(streaming=streaming)
        self._data = data

    def _read_data(self, task_ctx: TaskContext) -> Any:
        return self._data


class SimpleCallDataInputSource(BaseInputSource):
    """The implementation of InputSource for call data."""

    def __init__(self) -> None:
        """Create a SimpleCallDataInputSource."""
        super().__init__()

    def _read_data(self, task_ctx: TaskContext) -> Any:
        """Read data from task context.

        Returns:
            Any: The data.

        Raises:
            ValueError: If the call data is empty.
        """
        call_data = task_ctx.call_data
        data = call_data.get("data", EMPTY_DATA) if call_data else EMPTY_DATA
        if is_empty_data(data):
            raise ValueError("No call data for current SimpleCallDataInputSource")
        return data


class DefaultTaskContext(TaskContext, Generic[T]):
    """The default implementation of TaskContext."""

    def __init__(
        self,
        task_id: str,
        task_state: TaskState,
        task_output: Optional[TaskOutput[T]] = None,
    ) -> None:
        """Create a DefaultTaskContext.

        Args:
            task_id (str): The task id.
            task_state (TaskState): The task state.
            task_output (Optional[TaskOutput[T]], optional): The task output. Defaults
                to None.
        """
        super().__init__()
        self._task_id = task_id
        self._task_state = task_state
        self._output: Optional[TaskOutput[T]] = task_output
        self._task_input: Optional[InputContext] = None
        self._metadata: Dict[str, Any] = {}

    @property
    def task_id(self) -> str:
        """Return the task id."""
        return self._task_id

    @property
    def task_input(self) -> InputContext:
        """Return the task input."""
        if not self._task_input:
            raise ValueError("No input for current task context")
        return self._task_input

    def set_task_input(self, input_ctx: InputContext) -> None:
        """Save the task input to current task."""
        self._task_input = input_ctx

    @property
    def task_output(self) -> TaskOutput:
        """Return the task output.

        Returns:
            TaskOutput: The task output.

        Raises:
            ValueError: If the task output is empty.
        """
        if not self._output:
            raise ValueError("No output for current task context")
        return self._output

    def set_task_output(self, task_output: TaskOutput) -> None:
        """Save the task output to current task.

        Args:
            task_output (TaskOutput): The task output.
        """
        self._output = task_output

    @property
    def current_state(self) -> TaskState:
        """Return the current task state."""
        return self._task_state

    def set_current_state(self, task_state: TaskState) -> None:
        """Save the current task state to current task."""
        self._task_state = task_state

    def new_ctx(self) -> TaskContext:
        """Create new task context with empty output."""
        if not self._output:
            raise ValueError("No output for current task context")
        new_output = self._output.new_output()
        return DefaultTaskContext(self._task_id, self._task_state, new_output)

    @property
    def metadata(self) -> Dict[str, Any]:
        """Return the metadata of current task.

        Returns:
            Dict[str, Any]: The metadata.
        """
        return self._metadata

    async def _call_data_to_output(self) -> Optional[TaskOutput[T]]:
        """Return the call data of current task.

        Returns:
            Optional[TaskOutput[T]]: The call data.
        """
        call_data = self.call_data
        if not call_data:
            return None
        input_source = SimpleCallDataInputSource()
        return await input_source.read(self)


class DefaultInputContext(InputContext):
    """The default implementation of InputContext.

    It wraps the all inputs from parent tasks and provide some basic data operations.
    """

    def __init__(self, outputs: List[TaskContext]) -> None:
        """Create a DefaultInputContext.

        Args:
            outputs (List[TaskContext]): The outputs from parent tasks.
        """
        super().__init__()
        self._outputs = outputs

    @property
    def parent_outputs(self) -> List[TaskContext]:
        """Return the outputs from parent tasks.

        Returns:
            List[TaskContext]: The outputs from parent tasks.
        """
        return self._outputs

    async def _apply_func(
        self, func: Callable[[Any], Any], apply_type: str = "map"
    ) -> Tuple[List[TaskContext], List[TaskOutput]]:
        """Apply the function to all parent outputs.

        Args:
            func (Callable[[Any], Any]): The function to apply.
            apply_type (str, optional): The apply type. Defaults to "map".

        Returns:
            Tuple[List[TaskContext], List[TaskOutput]]: The new parent outputs and the
                results of applying the function.
        """
        new_outputs: List[TaskContext] = []
        map_tasks = []
        for out in self._outputs:
            new_outputs.append(out.new_ctx())
            if apply_type == "map":
                result: Coroutine[Any, Any, TaskOutput[Any]] = out.task_output.map(func)
            elif apply_type == "reduce":
                reduce_func = cast(ReduceFunc, func)
                result = out.task_output.reduce(reduce_func)
            elif apply_type == "check_condition":
                result = out.task_output.check_condition(func)
            else:
                raise ValueError(f"Unsupport apply type {apply_type}")
            map_tasks.append(result)
        results = await asyncio.gather(*map_tasks)
        return new_outputs, results

    async def map(self, map_func: Callable[[Any], Any]) -> InputContext:
        """Apply a mapping function to all parent outputs."""
        new_outputs, results = await self._apply_func(map_func)
        for i, task_ctx in enumerate(new_outputs):
            task_ctx = cast(TaskContext, task_ctx)
            task_ctx.set_task_output(results[i])
        return DefaultInputContext(new_outputs)

    async def map_all(self, map_func: Callable[..., Any]) -> InputContext:
        """Apply a mapping function to all parent outputs.

        The parent outputs will be unpacked and passed to the mapping function.

        Args:
            map_func (Callable[..., Any]): The mapping function.

        Returns:
            InputContext: The new input context.
        """
        if not self._outputs:
            return DefaultInputContext([])
        # Some parent may be empty
        not_empty_idx = 0
        for i, p in enumerate(self._outputs):
            if p.task_output.is_empty:
                # Skip empty parent
                continue
            not_empty_idx = i
            break
        # All output is empty?
        is_steam = self._outputs[not_empty_idx].task_output.is_stream
        if is_steam and not self.check_stream(skip_empty=True):
            raise ValueError(
                "The output in all tasks must has same output format to map_all"
            )
        outputs = []
        for out in self._outputs:
            if out.task_output.is_stream:
                outputs.append(out.task_output.output_stream)
            else:
                outputs.append(out.task_output.output)
        if asyncio.iscoroutinefunction(map_func):
            map_res = await map_func(*outputs)
        else:
            map_res = map_func(*outputs)
        single_output: TaskContext = self._outputs[not_empty_idx].new_ctx()
        single_output.task_output.set_output(map_res)
        logger.debug(
            f"Current map_all map_res: {map_res}, is steam: "
            f"{single_output.task_output.is_stream}"
        )
        return DefaultInputContext([single_output])

    async def reduce(self, reduce_func: ReduceFunc) -> InputContext:
        """Apply a reduce function to all parent outputs."""
        if not self.check_stream():
            raise ValueError(
                "The output in all tasks must has same output format of stream to apply"
                " reduce function"
            )
        new_outputs, results = await self._apply_func(
            reduce_func, apply_type="reduce"  # type: ignore
        )
        for i, task_ctx in enumerate(new_outputs):
            task_ctx = cast(TaskContext, task_ctx)
            task_ctx.set_task_output(results[i])
        return DefaultInputContext(new_outputs)

    async def filter(self, filter_func: Callable[[Any], bool]) -> InputContext:
        """Filter all parent outputs."""
        new_outputs, results = await self._apply_func(
            filter_func, apply_type="check_condition"
        )
        result_outputs = []
        for i, task_ctx in enumerate(new_outputs):
            if results[i]:
                result_outputs.append(task_ctx)
        return DefaultInputContext(result_outputs)

    async def predicate_map(
        self, predicate_func: PredicateFunc, failed_value: Any = None
    ) -> "InputContext":
        """Apply a predicate function to all parent outputs."""
        new_outputs, results = await self._apply_func(
            predicate_func, apply_type="check_condition"
        )
        result_outputs = []
        for i, task_ctx in enumerate(new_outputs):
            task_ctx = cast(TaskContext, task_ctx)
            if not results[i].is_empty:
                task_ctx.task_output.set_output(True)
                result_outputs.append(task_ctx)
            else:
                task_ctx.task_output.set_output(failed_value)
                result_outputs.append(task_ctx)
        return DefaultInputContext(result_outputs)
