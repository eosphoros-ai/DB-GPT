import uuid
import json
import asyncio
import time
import os
from fastapi import (
    APIRouter,
    Request,
    Body,
    status,
    HTTPException,
    Response,
    BackgroundTasks,
)

from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from typing import List

from pilot.openapi.api_v1.api_view_model import (
    Result,
    ConversationVo,
    MessageVo,
    ChatSceneVo,
)
from pilot.configs.config import Config
from pilot.server.knowledge.service import KnowledgeService
from pilot.server.knowledge.request.request import KnowledgeSpaceRequest

from pilot.scene.base_chat import BaseChat
from pilot.scene.base import ChatScene
from pilot.scene.chat_factory import ChatFactory
from pilot.configs.model_config import LOGDIR
from pilot.utils import build_logger
from pilot.scene.base_message import BaseMessage
from pilot.memory.chat_history.duckdb_history import DuckdbHistoryMemory
from pilot.scene.message import OnceConversation

router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = build_logger("api_v1", LOGDIR + "api_v1.log")
knowledge_service = KnowledgeService()

model_semaphore = None
global_counter = 0
static_file_path = os.path.join(os.getcwd(), "server/static")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    message = ""
    for error in exc.errors():
        message += ".".join(error.get("loc")) + ":" + error.get("msg") + ";"
    return Result.faild(code="E0001", msg=message)


def __get_conv_user_message(conversations: dict):
    messages = conversations["messages"]
    for item in messages:
        if item["type"] == "human":
            return item["data"]["content"]
    return ""


def __new_conversation(chat_mode, user_id) -> ConversationVo:
    unique_id = uuid.uuid1()
    # history_mem = DuckdbHistoryMemory(str(unique_id))
    return ConversationVo(conv_uid=str(unique_id), chat_mode=chat_mode)


def get_db_list():
    db = CFG.local_db
    dbs = db.get_database_list()
    params: dict = {}
    for name in dbs:
        params.update({name: name})
    return params


def plugins_select_info():
    plugins_infos: dict = {}
    for plugin in CFG.plugins:
        plugins_infos.update({f"【{plugin._name}】=>{plugin._description}": plugin._name})
    return plugins_infos


def knowledge_list():
    """return knowledge space list"""
    params: dict = {}
    request = KnowledgeSpaceRequest()
    spaces = knowledge_service.get_knowledge_space(request)
    for space in spaces:
        params.update({space.name: space.name})
    return params


@router.get("/v1/chat/dialogue/list", response_model=Result[ConversationVo])
async def dialogue_list(user_id: str = None):
    dialogues: List = []
    datas = DuckdbHistoryMemory.conv_list(user_id)

    for item in datas:
        conv_uid = item.get("conv_uid")
        summary = item.get("summary")
        chat_mode = item.get("chat_mode")

        conv_vo: ConversationVo = ConversationVo(
            conv_uid=conv_uid,
            user_input=summary,
            chat_mode=chat_mode,
        )
        dialogues.append(conv_vo)

    return Result[ConversationVo].succ(dialogues[:10])


@router.post("/v1/chat/dialogue/scenes", response_model=Result[List[ChatSceneVo]])
async def dialogue_scenes():
    scene_vos: List[ChatSceneVo] = []
    new_modes: List[ChatScene] = [
        ChatScene.ChatWithDbExecute,
        ChatScene.ChatWithDbQA,
        ChatScene.ChatKnowledge,
        ChatScene.ChatDashboard,
        ChatScene.ChatExecution,
    ]
    for scene in new_modes:
        scene_vo = ChatSceneVo(
            chat_scene=scene.value(),
            scene_name=scene.scene_name(),
            scene_describe=scene.describe(),
            param_title=",".join(scene.param_types()),
        )
        scene_vos.append(scene_vo)
    return Result.succ(scene_vos)


@router.post("/v1/chat/dialogue/new", response_model=Result[ConversationVo])
async def dialogue_new(
    chat_mode: str = ChatScene.ChatNormal.value(), user_id: str = None
):
    conv_vo = __new_conversation(chat_mode, user_id)
    return Result.succ(conv_vo)


@router.post("/v1/chat/mode/params/list", response_model=Result[dict])
async def params_list(chat_mode: str = ChatScene.ChatNormal.value()):
    if ChatScene.ChatWithDbQA.value() == chat_mode:
        return Result.succ(get_db_list())
    elif ChatScene.ChatWithDbExecute.value() == chat_mode:
        return Result.succ(get_db_list())
    elif ChatScene.ChatDashboard.value() == chat_mode:
        return Result.succ(get_db_list())
    elif ChatScene.ChatExecution.value() == chat_mode:
        return Result.succ(plugins_select_info())
    elif ChatScene.ChatKnowledge.value() == chat_mode:
        return Result.succ(knowledge_list())
    else:
        return Result.succ(None)


@router.post("/v1/chat/dialogue/delete")
async def dialogue_delete(con_uid: str):
    history_mem = DuckdbHistoryMemory(con_uid)
    history_mem.delete()
    return Result.succ(None)


@router.get("/v1/chat/dialogue/messages/history", response_model=Result[MessageVo])
async def dialogue_history_messages(con_uid: str):
    print(f"dialogue_history_messages:{con_uid}")
    message_vos: List[MessageVo] = []

    history_mem = DuckdbHistoryMemory(con_uid)
    history_messages: List[OnceConversation] = history_mem.get_messages()
    if history_messages:
        for once in history_messages:
            once_message_vos = [
                message2Vo(element, once["chat_order"]) for element in once["messages"]
            ]
            message_vos.extend(once_message_vos)
    return Result.succ(message_vos)


@router.post("/v1/chat/completions")
async def chat_completions(dialogue: ConversationVo = Body()):
    print(f"chat_completions:{dialogue.chat_mode},{dialogue.select_param}")
    if not dialogue.chat_mode:
        dialogue.chat_mode = ChatScene.ChatNormal.value()
    if not dialogue.conv_uid:
        conv_vo = __new_conversation(dialogue.chat_mode, dialogue.user_name)
        dialogue.conv_uid = conv_vo.conv_uid

    global model_semaphore, global_counter
    global_counter += 1
    if model_semaphore is None:
        model_semaphore = asyncio.Semaphore(CFG.LIMIT_MODEL_CONCURRENCY)
    await model_semaphore.acquire()

    if not ChatScene.is_valid_mode(dialogue.chat_mode):
        raise StopAsyncIteration(
            Result.faild("Unsupported Chat Mode," + dialogue.chat_mode + "!")
        )

    chat_param = {
        "chat_session_id": dialogue.conv_uid,
        "user_input": dialogue.user_input,
    }

    if ChatScene.ChatWithDbQA.value() == dialogue.chat_mode:
        chat_param.update({"db_name": dialogue.select_param})
    elif ChatScene.ChatWithDbExecute.value() == dialogue.chat_mode:
        chat_param.update({"db_name": dialogue.select_param})
    elif ChatScene.ChatDashboard.value() == dialogue.chat_mode:
        chat_param.update({"db_name": dialogue.select_param})
        ## DEFAULT
        chat_param.update({"report_name": "sales_report"})
    elif ChatScene.ChatExecution.value() == dialogue.chat_mode:
        chat_param.update({"plugin_selector": dialogue.select_param})
    elif ChatScene.ChatKnowledge.value() == dialogue.chat_mode:
        chat_param.update({"knowledge_space": dialogue.select_param})

    chat: BaseChat = CHAT_FACTORY.get_implementation(dialogue.chat_mode, **chat_param)
    background_tasks = BackgroundTasks()
    background_tasks.add_task(release_model_semaphore)
    headers = {
        # "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        # "Transfer-Encoding": "chunked",
    }

    if not chat.prompt_template.stream_out:
        return StreamingResponse(
            no_stream_generator(chat),
            headers=headers,
            media_type="text/event-stream",
            background=background_tasks,
        )
    else:
        return StreamingResponse(
            stream_generator(chat),
            headers=headers,
            media_type="text/plain",
            background=background_tasks,
        )


def release_model_semaphore():
    model_semaphore.release()


async def no_stream_generator(chat):
    msg = chat.nostream_call()
    msg = msg.replace("\n", "\\n")
    yield f"data: {msg}\n\n"


async def stream_generator(chat):
    model_response = chat.stream_call()
    if not CFG.NEW_SERVER_MODE:
        for chunk in model_response.iter_lines(decode_unicode=False, delimiter=b"\0"):
            if chunk:
                msg = chat.prompt_template.output_parser.parse_model_stream_resp_ex(
                    chunk, chat.skip_echo_len
                )
                msg = msg.replace("\n", "\\n")
                yield f"data:{msg}\n\n"
                await asyncio.sleep(0.02)
    else:
        for chunk in model_response:
            if chunk:
                msg = chat.prompt_template.output_parser.parse_model_stream_resp_ex(
                    chunk, chat.skip_echo_len
                )

                msg = msg.replace("\n", "\\n")
                yield f"data:{msg}\n\n"
                await asyncio.sleep(0.02)

    chat.current_message.add_ai_message(msg)
    chat.current_message.add_view_message(msg)
    chat.memory.append(chat.current_message)


def message2Vo(message: dict, order) -> MessageVo:
    return MessageVo(
        role=message["type"], context=message["data"]["content"], order=order
    )
