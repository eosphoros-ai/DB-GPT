import uuid

from fastapi import APIRouter, Request, Body, status

from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from typing import List

from pilot.server.api_v1.api_view_model import Result, ConversationVo, MessageVo
from pilot.configs.config import Config
from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.scene.chat_factory import ChatFactory
from pilot.configs.model_config import (LOGDIR)
from pilot.utils import build_logger
from pilot.scene.base_message import (BaseMessage)

router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = build_logger("api_v1", LOGDIR + "api_v1.log")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = ""
    for error in exc.errors():
        message += ".".join(error.get("loc")) + ":" + error.get("msg") + ";"
    return Result.faild(message)


@router.get('/v1/chat/dialogue/list', response_model=Result[List[ConversationVo]])
async def dialogue_list(user_id: str):
    #### TODO

    conversations = [ConversationVo(conv_uid="123", chat_mode="user", select_param="test1", user_input="message[0]"),
                     ConversationVo(conv_uid="123", chat_mode="user", select_param="test1", user_input="message[0]")]

    return Result[ConversationVo].succ(conversations)


@router.post('/v1/chat/dialogue/new', response_model=Result[str])
async def dialogue_new(user_id: str):
    unique_id = uuid.uuid1()
    return Result.succ(unique_id)


@router.post('/v1/chat/dialogue/delete')
async def dialogue_delete(con_uid: str, user_id: str):
    #### TODO
    return Result.succ(None)


@router.post('/v1/chat/completions', response_model=Result[MessageVo])
async def chat_completions(dialogue: ConversationVo = Body()):
    print(f"chat_completions:{dialogue.chat_mode},{dialogue.select_param}")

    if not ChatScene.is_valid_mode(dialogue.chat_mode):
        raise StopAsyncIteration(Result.faild("Unsupported Chat Mode," + dialogue.chat_mode + "!"))

    chat_param = {
        "chat_session_id": dialogue.conv_uid,
        "user_input": dialogue.user_input,
    }

    if ChatScene.ChatWithDbExecute == dialogue.chat_mode:
        chat_param.update("db_name", dialogue.select_param)
    elif ChatScene.ChatWithDbQA == dialogue.chat_mode:
        chat_param.update("db_name", dialogue.select_param)
    elif ChatScene.ChatExecution == dialogue.chat_mode:
        chat_param.update("plugin_selector", dialogue.select_param)
    elif ChatScene.ChatNewKnowledge == dialogue.chat_mode:
        chat_param.update("knowledge_name", dialogue.select_param)
    elif ChatScene.ChatUrlKnowledge == dialogue.chat_mode:
        chat_param.update("url", dialogue.select_param)

    chat: BaseChat = CHAT_FACTORY.get_implementation(dialogue.chat_mode, **chat_param)
    if not chat.prompt_template.stream_out:
        return non_stream_response(chat)
    else:
        return stream_response(chat)


def stream_generator(chat):
    model_response = chat.stream_call()
    for chunk in model_response.iter_lines(decode_unicode=False, delimiter=b"\0"):
        if chunk:
            msg = chat.prompt_template.output_parser.parse_model_stream_resp_ex(chunk, chat.skip_echo_len)
            chat.current_message.add_ai_message(msg)
            messageVos = [message2Vo(element) for element in chat.current_message.messages]
            yield Result.succ(messageVos)
def stream_response(chat):
    logger.info("stream out start!")
    api_response = StreamingResponse(stream_generator(chat), media_type="application/json")
    return api_response

def message2Vo(message:BaseMessage)->MessageVo:
    vo:MessageVo = MessageVo()
    vo.role = message.type
    vo.role = message.content
    vo.time_stamp = message.additional_kwargs.time_stamp if message.additional_kwargs["time_stamp"] else 0

def non_stream_response(chat):
    logger.info("not stream out, wait model response!")
    chat.nostream_call()
    messageVos = [message2Vo(element) for element in chat.current_message.messages]
    return Result.succ(messageVos)


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
