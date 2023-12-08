import asyncio
from typing import Coroutine, List, Any


from dbgpt.app.scene import BaseChat, ChatFactory

chat_factory = ChatFactory()


async def llm_chat_response_nostream(chat_scene: str, **chat_param):
    """llm_chat_response_nostream"""
    chat: BaseChat = chat_factory.get_implementation(chat_scene, **chat_param)
    res = await chat.get_llm_response()
    return res


async def llm_chat_response(chat_scene: str, **chat_param):
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
