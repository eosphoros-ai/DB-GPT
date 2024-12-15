import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Coroutine, List


async def llm_chat_response_nostream(chat_scene: str, **chat_param):
    """llm_chat_response_nostream"""
    from dbgpt.app.scene import BaseChat, ChatFactory

    chat_factory = ChatFactory()
    chat: BaseChat = chat_factory.get_implementation(chat_scene, **chat_param)
    res = await chat.get_llm_response()
    return res


async def llm_chat_response(chat_scene: str, **chat_param):
    from dbgpt.app.scene import BaseChat, ChatFactory

    chat_factory = ChatFactory()
    chat: BaseChat = chat_factory.get_implementation(chat_scene, **chat_param)
    return chat.stream_call()


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
