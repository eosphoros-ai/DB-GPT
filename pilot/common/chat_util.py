import asyncio

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
