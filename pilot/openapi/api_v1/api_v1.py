import uuid
import json
import asyncio
import time
from fastapi import APIRouter, Request, Body, status, HTTPException, Response

from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from typing import List

from pilot.server.api_v1.api_view_model import Result, ConversationVo, MessageVo, ChatSceneVo
from pilot.configs.config import Config
from pilot.openapi.knowledge.knowledge_service import KnowledgeService
from pilot.openapi.knowledge.request.knowledge_request import KnowledgeSpaceRequest
from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.scene.chat_factory import ChatFactory
from pilot.configs.model_config import (LOGDIR)
from pilot.utils import build_logger
from pilot.scene.base_message import (BaseMessage)
from pilot.memory.chat_history.duckdb_history import DuckdbHistoryMemory
from pilot.scene.message import OnceConversation

router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = build_logger("api_v1", LOGDIR + "api_v1.log")
knowledge_service = KnowledgeService()


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = ""
    for error in exc.errors():
        message += ".".join(error.get("loc")) + ":" + error.get("msg") + ";"
    return Result.faild(msg=message)


def __get_conv_user_message(conversations: dict):
    messages = conversations['messages']
    for item in messages:
        if item['type'] == "human":
            return item['data']['content']
    return ""


@router.get('/v1/chat/dialogue/list', response_model=Result[ConversationVo])
async def dialogue_list(response: Response, user_id: str = None):
    # 设置CORS头部信息
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET'
    response.headers['Access-Control-Request-Headers'] = 'content-type'

    dialogues: List = []
    datas = DuckdbHistoryMemory.conv_list(user_id)

    for item in datas:
        conv_uid = item.get("conv_uid")
        messages = item.get("messages")
        conversations = json.loads(messages)

        first_conv: OnceConversation = conversations[0]
        conv_vo: ConversationVo = ConversationVo(conv_uid=conv_uid, user_input=__get_conv_user_message(first_conv),
                                                 chat_mode=first_conv['chat_mode'])
        dialogues.append(conv_vo)

    return Result[ConversationVo].succ(dialogues)


@router.post('/v1/chat/dialogue/scenes', response_model=Result[List[ChatSceneVo]])
async def dialogue_scenes():
    scene_vos: List[ChatSceneVo] = []
    new_modes:List[ChatScene] = [ChatScene.ChatDb, ChatScene.ChatData, ChatScene.ChatDashboard, ChatScene.ChatKnowledge, ChatScene.ChatExecution]
    for scene in new_modes:
        if not scene.value in [ChatScene.ChatNormal.value, ChatScene.InnerChatDBSummary.value]:
            scene_vo = ChatSceneVo(chat_scene=scene.value, scene_name=scene.name, param_title="Selection Param")
            scene_vos.append(scene_vo)
    return Result.succ(scene_vos)


@router.post('/v1/chat/dialogue/new', response_model=Result[ConversationVo])
async def dialogue_new(chat_mode: str = ChatScene.ChatNormal.value, user_id: str = None):
    unique_id = uuid.uuid1()
    return Result.succ(ConversationVo(conv_uid=str(unique_id), chat_mode=chat_mode))


def get_db_list():
    db = CFG.local_db
    dbs = db.get_database_list()
    params:dict = {}
    for name in dbs:
        params.update({name: name})
    return params


def plugins_select_info():
    plugins_infos: dict = {}
    for plugin in CFG.plugins:
        plugins_infos.update({f"【{plugin._name}】=>{plugin._description}": plugin._name})
    return plugins_infos


def knowledge_list():
    request = KnowledgeSpaceRequest()
    return knowledge_service.get_knowledge_space(request)


@router.post('/v1/chat/mode/params/list', response_model=Result[dict])
async def params_list(chat_mode: str = ChatScene.ChatNormal.value):
    if ChatScene.ChatDb.value == chat_mode:
        return Result.succ(get_db_list())
    elif ChatScene.ChatData.value == chat_mode:
        return Result.succ(get_db_list())
    elif ChatScene.ChatDashboard.value == chat_mode:
        return Result.succ(get_db_list())
    elif ChatScene.ChatExecution.value == chat_mode:
        return Result.succ(plugins_select_info())
    elif ChatScene.ChatKnowledge.value == chat_mode:
        return Result.succ(knowledge_list())
    else:
        return Result.succ(None)


@router.post('/v1/chat/dialogue/delete')
async def dialogue_delete(con_uid: str):
    history_mem = DuckdbHistoryMemory(con_uid)
    history_mem.delete()
    return Result.succ(None)


@router.get('/v1/chat/dialogue/messages/history', response_model=Result[MessageVo])
async def dialogue_history_messages(con_uid: str):
    print(f"dialogue_history_messages:{con_uid}")
    message_vos: List[MessageVo] = []

    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        for once in history_messages:
            once_message_vos = [message2Vo(element, once['chat_order']) for element in once['messages']]
            message_vos.extend(once_message_vos)
    return Result.succ(message_vos)


@router.post('/v1/chat/completions')
async def chat_completions(dialogue: ConversationVo = Body()):
    print(f"chat_completions:{dialogue.chat_mode},{dialogue.select_param}")

    if not ChatScene.is_valid_mode(dialogue.chat_mode):
        raise StopAsyncIteration(Result.faild("Unsupported Chat Mode," + dialogue.chat_mode + "!"))

    chat_param = {
        "chat_session_id": dialogue.conv_uid,
        "user_input": dialogue.user_input,
    }

    if ChatScene.ChatDb == dialogue.chat_mode:
        chat_param.update("db_name", dialogue.select_param)
    elif ChatScene.ChatData == dialogue.chat_mode:
        chat_param.update("db_name", dialogue.select_param)
    elif ChatScene.ChatDashboard == dialogue.chat_mode:
        chat_param.update("db_name", dialogue.select_param)
    elif ChatScene.ChatExecution == dialogue.chat_mode:
        chat_param.update("plugin_selector", dialogue.select_param)
    elif ChatScene.ChatKnowledge == dialogue.chat_mode:
        chat_param.update("knowledge_space", dialogue.select_param)

    chat: BaseChat = CHAT_FACTORY.get_implementation(dialogue.chat_mode, **chat_param)
    if not chat.prompt_template.stream_out:
        return non_stream_response(chat)
    else:
        # generator = stream_generator(chat)
        # result = Result.succ(data=StreamingResponse(stream_test(), media_type='text/plain'))
        # return result
        return StreamingResponse(stream_generator(chat), media_type="text/plain")


def stream_test():
    for message in ["Hello", "world", "how", "are", "you"]:
        yield message
        # yield json.dumps(Result.succ(message).__dict__).encode("utf-8")


def stream_generator(chat):
    model_response = chat.stream_call()
    for chunk in model_response.iter_lines(decode_unicode=False, delimiter=b"\0"):
        if chunk:
            msg = chat.prompt_template.output_parser.parse_model_stream_resp_ex(chunk, chat.skip_echo_len)
            chat.current_message.add_ai_message(msg)
            yield msg
            # chat.current_message.add_ai_message(msg)
            # vo = MessageVo(role="view", context=msg, order=chat.current_message.chat_order)
            # json_text = json.dumps(vo.__dict__)
            # yield json_text.encode('utf-8')
    chat.memory.append(chat.current_message)


# def stream_response(chat):
#     logger.info("stream out start!")
#     api_response = StreamingResponse(stream_generator(chat), media_type="application/json")
#     return api_response


def message2Vo(message: dict, order) -> MessageVo:
    # message.additional_kwargs['time_stamp'] if message.additional_kwargs["time_stamp"] else 0
    return MessageVo(role=message['type'], context=message['data']['content'], order=order)


def non_stream_response(chat):
    logger.info("not stream out, wait model response!")
    return chat.nostream_call()


@router.get('/v1/db/types', response_model=Result[str])
async def db_types():
    return Result.succ(["mysql", "duckdb"])


@router.get('/v1/db/list', response_model=Result[str])
async def db_list():
    db = CFG.local_db
    dbs = db.get_database_list()
    return Result.succ(dbs)


@router.get('/v1/knowledge/list')
async def knowledge_list():
    return ["test1", "test2"]


@router.post('/v1/knowledge/add')
async def knowledge_add():
    return ["test1", "test2"]


@router.post('/v1/knowledge/delete')
async def knowledge_delete():
    return ["test1", "test2"]


@router.get('/v1/knowledge/types')
async def knowledge_types():
    return ["test1", "test2"]


@router.get('/v1/knowledge/detail')
async def knowledge_detail():
    return ["test1", "test2"]
