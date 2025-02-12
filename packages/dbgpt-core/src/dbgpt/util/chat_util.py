import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Coroutine, List, Union

from dbgpt._private.pydantic import BaseModel, model_to_json

SSE_DATA_TYPE = Union[str, BaseModel, dict]


async def run_async_tasks(
    tasks: List[Coroutine],
    concurrency_limit: int = None,
) -> List[Any]:
    """Run a list of async tasks."""
    tasks_to_execute: List[Any] = tasks

    async def _gather() -> List[Any]:
        if concurrency_limit:
            semaphore = asyncio.Semaphore(concurrency_limit)

            async def _execute_task(task):
                async with semaphore:
                    return await task

            # Execute tasks with semaphore limit
            return await asyncio.gather(
                *[_execute_task(task) for task in tasks_to_execute]
            )
        else:
            return await asyncio.gather(*tasks_to_execute)

    # outputs: List[Any] = asyncio.run(_gather())
    return await _gather()


def run_tasks(
    tasks: List[Callable],
    concurrency_limit: int = None,
) -> List[Any]:
    """
    Run a list of tasks concurrently using a thread pool.

    Args:
        tasks: List of callable functions to execute
        concurrency_limit: Maximum number of concurrent threads (optional)

    Returns:
        List of results from all tasks in the order they were submitted
    """
    max_workers = concurrency_limit if concurrency_limit else None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks and get futures
        futures = [executor.submit(task) for task in tasks]

        # Collect results in order, raising any exceptions
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except Exception as e:
                # Cancel any pending futures
                for f in futures:
                    f.cancel()
                raise e

    return results


def transform_to_sse(data: SSE_DATA_TYPE) -> str:
    """Transform data to Server-Sent Events format.

    Args:
        data: Data to transform to SSE format

    Returns:
        str: Data in SSE format

    Raises:
        ValueError: If data type is not supported
    """
    if isinstance(data, BaseModel):
        return (
            f"data: {model_to_json(data, exclude_unset=True, ensure_ascii=False)}\n\n"
        )
    elif isinstance(data, dict):
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
    elif isinstance(data, str):
        return f"data: {data}\n\n"
    elif is_dataclass(data):
        return f"data: {json.dumps(asdict(data), ensure_ascii=False)}\n\n"
    else:
        raise ValueError(f"Unsupported data type: {type(data)}")
