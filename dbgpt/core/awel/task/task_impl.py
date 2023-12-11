from abc import ABC, abstractmethod
from typing import (
    Callable,
    Coroutine,
    Iterator,
    AsyncIterator,
    List,
    Generic,
    TypeVar,
    Any,
    Tuple,
    Dict,
    Union,
    Optional,
)
import asyncio
import logging
from .base import TaskOutput, TaskContext, TaskState, InputContext, InputSource, T


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
    def __init__(self, data: T) -> None:
        super().__init__()
        self._data = data

    @property
    def output(self) -> T:
        return self._data

    def set_output(self, output_data: T | AsyncIterator[T]) -> None:
        self._data = output_data

    def new_output(self) -> TaskOutput[T]:
        return SimpleTaskOutput(None)

    @property
    def is_empty(self) -> bool:
        return self._data is None

    async def _apply_func(self, func) -> Any:
        if asyncio.iscoroutinefunction(func):
            out = await func(self._data)
        else:
            out = func(self._data)
        return out

    async def map(self, map_func) -> TaskOutput[T]:
        out = await self._apply_func(map_func)
        return SimpleTaskOutput(out)

    async def check_condition(self, condition_func) -> bool:
        return await self._apply_func(condition_func)

    async def streamify(
        self, transform_func: Callable[[T], AsyncIterator[T]]
    ) -> TaskOutput[T]:
        out = await self._apply_func(transform_func)
        return SimpleStreamTaskOutput(out)


class SimpleStreamTaskOutput(TaskOutput[T], Generic[T]):
    def __init__(self, data: AsyncIterator[T]) -> None:
        super().__init__()
        self._data = data

    @property
    def is_stream(self) -> bool:
        return True

    @property
    def is_empty(self) -> bool:
        return not self._data

    @property
    def output_stream(self) -> AsyncIterator[T]:
        return self._data

    def set_output(self, output_data: T | AsyncIterator[T]) -> None:
        self._data = output_data

    def new_output(self) -> TaskOutput[T]:
        return SimpleStreamTaskOutput(None)

    async def map(self, map_func) -> TaskOutput[T]:
        is_async = asyncio.iscoroutinefunction(map_func)

        async def new_iter() -> AsyncIterator[T]:
            async for out in self._data:
                if is_async:
                    out = await map_func(out)
                else:
                    out = map_func(out)
                yield out

        return SimpleStreamTaskOutput(new_iter())

    async def reduce(self, reduce_func) -> TaskOutput[T]:
        out = await _reduce_stream(self._data, reduce_func)
        return SimpleTaskOutput(out)

    async def unstreamify(
        self, transform_func: Callable[[AsyncIterator[T]], T]
    ) -> TaskOutput[T]:
        if asyncio.iscoroutinefunction(transform_func):
            out = await transform_func(self._data)
        else:
            out = transform_func(self._data)
        return SimpleTaskOutput(out)

    async def transform_stream(
        self, transform_func: Callable[[AsyncIterator[T]], AsyncIterator[T]]
    ) -> TaskOutput[T]:
        if asyncio.iscoroutinefunction(transform_func):
            out = await transform_func(self._data)
        else:
            out = transform_func(self._data)
        return SimpleStreamTaskOutput(out)


def _is_async_iterator(obj):
    return (
        hasattr(obj, "__anext__")
        and callable(getattr(obj, "__anext__", None))
        and hasattr(obj, "__aiter__")
        and callable(getattr(obj, "__aiter__", None))
    )


class BaseInputSource(InputSource, ABC):
    def __init__(self) -> None:
        super().__init__()
        self._is_read = False

    @abstractmethod
    def _read_data(self, task_ctx: TaskContext) -> Any:
        """Read data with task context"""

    async def read(self, task_ctx: TaskContext) -> TaskOutput:
        data = self._read_data(task_ctx)
        if _is_async_iterator(data):
            if self._is_read:
                raise ValueError(f"Input iterator {data} has been read!")
            output = SimpleStreamTaskOutput(data)
        else:
            output = SimpleTaskOutput(data)
        self._is_read = True
        return output


class SimpleInputSource(BaseInputSource):
    def __init__(self, data: Any) -> None:
        super().__init__()
        self._data = data

    def _read_data(self, task_ctx: TaskContext) -> Any:
        return self._data


class SimpleCallDataInputSource(BaseInputSource):
    def __init__(self) -> None:
        super().__init__()

    def _read_data(self, task_ctx: TaskContext) -> Any:
        call_data = task_ctx.call_data
        data = call_data.get("data") if call_data else None
        if not (call_data and data):
            raise ValueError("No call data for current SimpleCallDataInputSource")
        return data


class DefaultTaskContext(TaskContext, Generic[T]):
    def __init__(
        self, task_id: str, task_state: TaskState, task_output: TaskOutput[T]
    ) -> None:
        super().__init__()
        self._task_id = task_id
        self._task_state = task_state
        self._output = task_output
        self._task_input = None
        self._metadata = {}

    @property
    def task_id(self) -> str:
        return self._task_id

    @property
    def task_input(self) -> InputContext:
        return self._task_input

    def set_task_input(self, input_ctx: "InputContext") -> None:
        self._task_input = input_ctx

    @property
    def task_output(self) -> TaskOutput:
        return self._output

    def set_task_output(self, task_output: TaskOutput) -> None:
        self._output = task_output

    @property
    def current_state(self) -> TaskState:
        return self._task_state

    def set_current_state(self, task_state: TaskState) -> None:
        self._task_state = task_state

    def new_ctx(self) -> TaskContext:
        new_output = self._output.new_output()
        return DefaultTaskContext(self._task_id, self._task_state, new_output)

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata

    async def _call_data_to_output(self) -> Optional[TaskOutput[T]]:
        """Get the call data for current data"""
        call_data = self.call_data
        if not call_data:
            return None
        input_source = SimpleCallDataInputSource()
        return await input_source.read(self)


class DefaultInputContext(InputContext):
    def __init__(self, outputs: List[TaskContext]) -> None:
        super().__init__()
        self._outputs = outputs

    @property
    def parent_outputs(self) -> List[TaskContext]:
        return self._outputs

    async def _apply_func(
        self, func: Callable[[Any], Any], apply_type: str = "map"
    ) -> Tuple[List[TaskContext], List[TaskOutput]]:
        new_outputs: List[TaskContext] = []
        map_tasks = []
        for out in self._outputs:
            new_outputs.append(out.new_ctx())
            result = None
            if apply_type == "map":
                result = out.task_output.map(func)
            elif apply_type == "reduce":
                result = out.task_output.reduce(func)
            elif apply_type == "check_condition":
                result = out.task_output.check_condition(func)
            else:
                raise ValueError(f"Unsupport apply type {apply_type}")
            map_tasks.append(result)
        results = await asyncio.gather(*map_tasks)
        return new_outputs, results

    async def map(self, map_func: Callable[[Any], Any]) -> InputContext:
        new_outputs, results = await self._apply_func(map_func)
        for i, task_ctx in enumerate(new_outputs):
            task_ctx: TaskContext = task_ctx
            task_ctx.set_task_output(results[i])
        return DefaultInputContext(new_outputs)

    async def map_all(self, map_func: Callable[..., Any]) -> InputContext:
        if not self._outputs:
            return DefaultInputContext([])
        # Some parent may be empty
        not_empty_idx = 0
        for i, p in enumerate(self._outputs):
            if p.task_output.is_empty:
                continue
            not_empty_idx = i
            break
        # All output is empty?
        is_steam = self._outputs[not_empty_idx].task_output.is_stream
        if is_steam:
            if not self.check_stream(skip_empty=True):
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
            f"Current map_all map_res: {map_res}, is steam: {single_output.task_output.is_stream}"
        )
        return DefaultInputContext([single_output])

    async def reduce(self, reduce_func: Callable[[Any], Any]) -> InputContext:
        if not self.check_stream():
            raise ValueError(
                "The output in all tasks must has same output format of stream to apply reduce function"
            )
        new_outputs, results = await self._apply_func(reduce_func, apply_type="reduce")
        for i, task_ctx in enumerate(new_outputs):
            task_ctx: TaskContext = task_ctx
            task_ctx.set_task_output(results[i])
        return DefaultInputContext(new_outputs)

    async def filter(self, filter_func: Callable[[Any], bool]) -> InputContext:
        new_outputs, results = await self._apply_func(
            filter_func, apply_type="check_condition"
        )
        result_outputs = []
        for i, task_ctx in enumerate(new_outputs):
            if results[i]:
                result_outputs.append(task_ctx)
        return DefaultInputContext(result_outputs)

    async def predicate_map(
        self, predicate_func: Callable[[Any], bool], failed_value: Any = None
    ) -> "InputContext":
        new_outputs, results = await self._apply_func(
            predicate_func, apply_type="check_condition"
        )
        result_outputs = []
        for i, task_ctx in enumerate(new_outputs):
            task_ctx: TaskContext = task_ctx
            if results[i]:
                task_ctx.task_output.set_output(True)
                result_outputs.append(task_ctx)
            else:
                task_ctx.task_output.set_output(failed_value)
                result_outputs.append(task_ctx)
        return DefaultInputContext(result_outputs)
