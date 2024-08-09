from typing import Any

from dbgpt.serve.core.config import BaseServeConfig
from dbgpt.serve.core.schemas import Result, add_exception_handler
from dbgpt.serve.core.serve import BaseServe
from dbgpt.serve.core.service import BaseService
from dbgpt.util.executor_utils import BlockingFunction, DefaultExecutorFactory
from dbgpt.util.executor_utils import blocking_func_to_async as _blocking_func_to_async

__ALL__ = [
    "Result",
    "add_exception_handler",
    "BaseServeConfig",
    "BaseService",
    "BaseServe",
]


async def blocking_func_to_async(
    system_app, func: BlockingFunction, *args, **kwargs
) -> Any:
    """Run a potentially blocking function within an executor."""
    executor = DefaultExecutorFactory.get_instance(system_app).create()
    return await _blocking_func_to_async(executor, func, *args, **kwargs)
