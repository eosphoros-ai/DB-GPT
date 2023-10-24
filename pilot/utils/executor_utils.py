from typing import Callable, Awaitable, Any
import asyncio
from abc import ABC, abstractmethod
from concurrent.futures import Executor, ThreadPoolExecutor
from functools import partial

from pilot.component import BaseComponent, ComponentType, SystemApp


class ExecutorFactory(BaseComponent, ABC):
    name = ComponentType.EXECUTOR_DEFAULT.value

    @abstractmethod
    def create(self) -> "Executor":
        """Create executor"""


class DefaultExecutorFactory(ExecutorFactory):
    def __init__(self, system_app: SystemApp | None = None, max_workers=None):
        super().__init__(system_app)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix=self.name
        )

    def init_app(self, system_app: SystemApp):
        pass

    def create(self) -> Executor:
        return self._executor


BlockingFunction = Callable[..., Any]


async def blocking_func_to_async(
    executor: Executor, func: BlockingFunction, *args, **kwargs
):
    """Run a potentially blocking function within an executor.

    Args:
        executor (Executor): The concurrent.futures.Executor to run the function within.
        func (ApplyFunction): The callable function, which should be a synchronous function.
            It should accept any number and type of arguments and return an asynchronous coroutine.
        *args (Any): Any additional arguments to pass to the function.
        **kwargs (Any): Other arguments to pass to the function

    Returns:
        Any: The result of the function's execution.

    Raises:
        ValueError: If the provided function 'func' is an asynchronous coroutine function.

    This function allows you to execute a potentially blocking function within an executor.
    It expects 'func' to be a synchronous function and will raise an error if 'func' is an asynchronous coroutine.
    """
    if asyncio.iscoroutinefunction(func):
        raise ValueError(f"The function {func} is not blocking function")
    loop = asyncio.get_event_loop()
    sync_function_noargs = partial(func, *args, **kwargs)
    return await loop.run_in_executor(executor, sync_function_noargs)
