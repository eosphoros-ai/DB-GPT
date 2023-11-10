import asyncio
from typing import Coroutine, List, Any

from starlette.responses import StreamingResponse

from pilot.scene.base_chat import BaseChat
from pilot.scene.chat_factory import ChatFactory

chat_factory = ChatFactory()


async def llm_chat_response_nostream(chat_scene: str, **chat_param):
    """llm_chat_response_nostream"""
    chat: BaseChat = chat_factory.get_implementation(chat_scene, **chat_param)
    res = await chat.get_llm_response()
    return res


async def llm_chat_response(chat_scene: str, **chat_param):
    chat: BaseChat = chat_factory.get_implementation(chat_scene, **chat_param)
    return chat.stream_call()


def run_async_tasks(
    tasks: List[Coroutine],
    show_progress: bool = False,
    progress_bar_desc: str = "Running async tasks",
) -> List[Any]:
    """Run a list of async tasks."""

    tasks_to_execute: List[Any] = tasks
    if show_progress:
        try:
            import nest_asyncio
            from tqdm.asyncio import tqdm

            nest_asyncio.apply()
            loop = asyncio.get_event_loop()

            async def _tqdm_gather() -> List[Any]:
                return await tqdm.gather(*tasks_to_execute, desc=progress_bar_desc)

            tqdm_outputs: List[Any] = loop.run_until_complete(_tqdm_gather())
            return tqdm_outputs
        # run the operation w/o tqdm on hitting a fatal
        # may occur in some environments where tqdm.asyncio
        # is not supported
        except Exception:
            pass

    async def _gather() -> List[Any]:
        return await asyncio.gather(*tasks_to_execute)

    outputs: List[Any] = asyncio.run(_gather())
    return outputs
