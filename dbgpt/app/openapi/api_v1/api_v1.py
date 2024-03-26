import asyncio
import logging
import os
import uuid
from concurrent.futures import Executor
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt.app.knowledge.request.request import KnowledgeSpaceRequest
from dbgpt.app.knowledge.service import KnowledgeService
from dbgpt.app.openapi.api_view_model import (
    ChatSceneVo,
    ConversationVo,
    MessageVo,
    Result,
)
from dbgpt.app.scene import BaseChat, ChatFactory, ChatScene
from dbgpt.component import ComponentType
from dbgpt.configs.model_config import KNOWLEDGE_UPLOAD_ROOT_PATH
from dbgpt.core.awel import CommonLLMHttpRequestBody
from dbgpt.core.schema.api import (
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    DeltaMessage,
)
from dbgpt.datasource.db_conn_info import DBConfig, DbTypeInfo
from dbgpt.model.base import FlatSupportedModel
from dbgpt.model.cluster import BaseModelController, WorkerManager, WorkerManagerFactory
from dbgpt.rag.summary.db_summary_client import DBSummaryClient
from dbgpt.serve.agent.agents.controller import multi_agents
from dbgpt.serve.flow.service.service import Service as FlowService
from dbgpt.util.executor_utils import (
    DefaultExecutorFactory,
    ExecutorFactory,
    blocking_func_to_async,
)
from dbgpt.util.tracer import SpanType, root_tracer

router = APIRouter()
CFG = Config()
CHAT_FACTORY = ChatFactory()
logger = logging.getLogger(__name__)
knowledge_service = KnowledgeService()

model_semaphore = None
global_counter = 0


def __get_conv_user_message(conversations: dict):
    messages = conversations["messages"]
    for item in messages:
        if item["type"] == "human":
            return item["data"]["content"]
    return ""


def __new_conversation(chat_mode, user_name: str, sys_code: str) -> ConversationVo:
    unique_id = uuid.uuid1()
    return ConversationVo(
        conv_uid=str(unique_id),
        chat_mode=chat_mode,
        user_name=user_name,
        sys_code=sys_code,
    )


def get_db_list():
    dbs = CFG.local_db_manager.get_db_list()
    db_params = []
    for item in dbs:
        params: dict = {}
        params.update({"param": item["db_name"]})
        params.update({"type": item["db_type"]})
        db_params.append(params)
    return db_params


def plugins_select_info():
    plugins_infos: dict = {}
    for plugin in CFG.plugins:
        plugins_infos.update({f"【{plugin._name}】=>{plugin._description}": plugin._name})
    return plugins_infos


def get_db_list_info():
    dbs = CFG.local_db_manager.get_db_list()
    params: dict = {}
    for item in dbs:
        comment = item["comment"]
        if comment is not None and len(comment) > 0:
            params.update({item["db_name"]: comment})
    return params


def knowledge_list_info():
    """return knowledge space list"""
    params: dict = {}
    request = KnowledgeSpaceRequest()
    spaces = knowledge_service.get_knowledge_space(request)
    for space in spaces:
        params.update({space.name: space.desc})
    return params


def knowledge_list():
    """return knowledge space list"""
    request = KnowledgeSpaceRequest()
    spaces = knowledge_service.get_knowledge_space(request)
    space_list = []
    for space in spaces:
        params: dict = {}
        params.update({"param": space.name})
        params.update({"type": "space"})
        space_list.append(params)
    return space_list


def get_model_controller() -> BaseModelController:
    controller = CFG.SYSTEM_APP.get_component(
        ComponentType.MODEL_CONTROLLER, BaseModelController
    )
    return controller


def get_worker_manager() -> WorkerManager:
    worker_manager = CFG.SYSTEM_APP.get_component(
        ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
    ).create()
    return worker_manager


def get_chat_flow() -> FlowService:
    """Get Chat Flow Service."""
    return FlowService.get_instance(CFG.SYSTEM_APP)


def get_executor() -> Executor:
    """Get the global default executor"""
    return CFG.SYSTEM_APP.get_component(
        ComponentType.EXECUTOR_DEFAULT,
        ExecutorFactory,
        or_register_component=DefaultExecutorFactory,
    ).create()


@router.get("/v1/chat/db/list", response_model=Result[DBConfig])
async def db_connect_list():
    return Result.succ(CFG.local_db_manager.get_db_list())


@router.post("/v1/chat/db/add", response_model=Result[bool])
async def db_connect_add(db_config: DBConfig = Body()):
    return Result.succ(CFG.local_db_manager.add_db(db_config))


@router.post("/v1/chat/db/edit", response_model=Result[bool])
async def db_connect_edit(db_config: DBConfig = Body()):
    return Result.succ(CFG.local_db_manager.edit_db(db_config))


@router.post("/v1/chat/db/delete", response_model=Result[bool])
async def db_connect_delete(db_name: str = None):
    return Result.succ(CFG.local_db_manager.delete_db(db_name))


async def async_db_summary_embedding(db_name, db_type):
    db_summary_client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
    db_summary_client.db_summary_embedding(db_name, db_type)


@router.post("/v1/chat/db/test/connect", response_model=Result[bool])
async def test_connect(db_config: DBConfig = Body()):
    try:
        # TODO Change the synchronous call to the asynchronous call
        CFG.local_db_manager.test_connect(db_config)
        return Result.succ(True)
    except Exception as e:
        return Result.failed(code="E1001", msg=str(e))


@router.post("/v1/chat/db/summary", response_model=Result[bool])
async def db_summary(db_name: str, db_type: str):
    # TODO Change the synchronous call to the asynchronous call
    async_db_summary_embedding(db_name, db_type)
    return Result.succ(True)


@router.get("/v1/chat/db/support/type", response_model=Result[DbTypeInfo])
async def db_support_types():
    support_types = CFG.local_db_manager.get_all_completed_types()
    db_type_infos = []
    for type in support_types:
        db_type_infos.append(
            DbTypeInfo(db_type=type.value(), is_file_db=type.is_file_db())
        )
    return Result[DbTypeInfo].succ(db_type_infos)


@router.post("/v1/chat/dialogue/scenes", response_model=Result[List[ChatSceneVo]])
async def dialogue_scenes():
    scene_vos: List[ChatSceneVo] = []
    new_modes: List[ChatScene] = [
        ChatScene.ChatWithDbExecute,
        ChatScene.ChatWithDbQA,
        ChatScene.ChatExcel,
        ChatScene.ChatKnowledge,
        ChatScene.ChatDashboard,
        ChatScene.ChatAgent,
    ]
    for scene in new_modes:
        scene_vo = ChatSceneVo(
            chat_scene=scene.value(),
            scene_name=scene.scene_name(),
            scene_describe=scene.describe(),
            param_title=",".join(scene.param_types()),
            show_disable=scene.show_disable(),
        )
        scene_vos.append(scene_vo)
    return Result.succ(scene_vos)


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
    elif ChatScene.ChatKnowledge.ExtractRefineSummary.value() == chat_mode:
        return Result.succ(knowledge_list())
    else:
        return Result.succ(None)


@router.post("/v1/chat/mode/params/file/load")
async def params_load(
    conv_uid: str,
    chat_mode: str,
    model_name: str,
    user_name: Optional[str] = None,
    sys_code: Optional[str] = None,
    doc_file: UploadFile = File(...),
):
    print(f"params_load: {conv_uid},{chat_mode},{model_name}")
    try:
        if doc_file:
            # Save the uploaded file
            upload_dir = os.path.join(KNOWLEDGE_UPLOAD_ROOT_PATH, chat_mode)
            os.makedirs(upload_dir, exist_ok=True)
            upload_path = os.path.join(upload_dir, doc_file.filename)
            async with aiofiles.open(upload_path, "wb") as f:
                await f.write(await doc_file.read())

            # Prepare the chat
            dialogue = ConversationVo(
                conv_uid=conv_uid,
                chat_mode=chat_mode,
                select_param=doc_file.filename,
                model_name=model_name,
                user_name=user_name,
                sys_code=sys_code,
            )
            chat: BaseChat = await get_chat_instance(dialogue)
            resp = await chat.prepare()

        # Refresh messages
        return Result.succ(get_hist_messages(conv_uid))
    except Exception as e:
        logger.error("excel load error!", e)
        return Result.failed(code="E000X", msg=f"File Load Error {str(e)}")


def get_hist_messages(conv_uid: str):
    from dbgpt.serve.conversation.serve import Service as ConversationService

    instance: ConversationService = ConversationService.get_instance(CFG.SYSTEM_APP)
    return instance.get_history_messages({"conv_uid": conv_uid})


async def get_chat_instance(dialogue: ConversationVo = Body()) -> BaseChat:
    logger.info(f"get_chat_instance:{dialogue}")
    if not dialogue.chat_mode:
        dialogue.chat_mode = ChatScene.ChatNormal.value()
    if not dialogue.conv_uid:
        conv_vo = __new_conversation(
            dialogue.chat_mode, dialogue.user_name, dialogue.sys_code
        )
        dialogue.conv_uid = conv_vo.conv_uid

    if not ChatScene.is_valid_mode(dialogue.chat_mode):
        raise StopAsyncIteration(f"Unsupported Chat Mode,{dialogue.chat_mode}!")

    chat_param = {
        "chat_session_id": dialogue.conv_uid,
        "user_name": dialogue.user_name,
        "sys_code": dialogue.sys_code,
        "current_user_input": dialogue.user_input,
        "select_param": dialogue.select_param,
        "model_name": dialogue.model_name,
    }
    chat: BaseChat = await blocking_func_to_async(
        get_executor(),
        CHAT_FACTORY.get_implementation,
        dialogue.chat_mode,
        **{"chat_param": chat_param},
    )
    return chat


@router.post("/v1/chat/prepare")
async def chat_prepare(dialogue: ConversationVo = Body()):
    # dialogue.model_name = CFG.LLM_MODEL
    logger.info(f"chat_prepare:{dialogue}")
    ## check conv_uid
    chat: BaseChat = await get_chat_instance(dialogue)
    if chat.has_history_messages():
        return Result.succ(None)
    resp = await chat.prepare()
    return Result.succ(resp)


@router.post("/v1/chat/completions")
async def chat_completions(
    dialogue: ConversationVo = Body(),
    flow_service: FlowService = Depends(get_chat_flow),
):
    print(
        f"chat_completions:{dialogue.chat_mode},{dialogue.select_param},{dialogue.model_name}"
    )
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    if dialogue.chat_mode == ChatScene.ChatAgent.value():
        return StreamingResponse(
            multi_agents.app_agent_chat(
                conv_uid=dialogue.conv_uid,
                gpts_name=dialogue.select_param,
                user_query=dialogue.user_input,
                user_code=dialogue.user_name,
                sys_code=dialogue.sys_code,
            ),
            headers=headers,
            media_type="text/event-stream",
        )
    elif dialogue.chat_mode == ChatScene.ChatFlow.value():
        flow_req = CommonLLMHttpRequestBody(
            model=dialogue.model_name,
            messages=dialogue.user_input,
            stream=True,
            # context=flow_ctx,
            # temperature=
            # max_new_tokens=
            # enable_vis=
            conv_uid=dialogue.conv_uid,
            span_id=root_tracer.get_current_span_id(),
            chat_mode=dialogue.chat_mode,
            chat_param=dialogue.select_param,
            user_name=dialogue.user_name,
            sys_code=dialogue.sys_code,
            incremental=dialogue.incremental,
        )
        return StreamingResponse(
            flow_service.chat_stream_flow_str(dialogue.select_param, flow_req),
            headers=headers,
            media_type="text/event-stream",
        )
    else:
        with root_tracer.start_span(
            "get_chat_instance", span_type=SpanType.CHAT, metadata=dialogue.dict()
        ):
            chat: BaseChat = await get_chat_instance(dialogue)

        if not chat.prompt_template.stream_out:
            return StreamingResponse(
                no_stream_generator(chat),
                headers=headers,
                media_type="text/event-stream",
            )
        else:
            return StreamingResponse(
                stream_generator(chat, dialogue.incremental, dialogue.model_name),
                headers=headers,
                media_type="text/plain",
            )


@router.get("/v1/model/types")
async def model_types(controller: BaseModelController = Depends(get_model_controller)):
    logger.info(f"/controller/model/types")
    try:
        types = set()
        models = await controller.get_all_instances(healthy_only=True)
        for model in models:
            worker_name, worker_type = model.model_name.split("@")
            if worker_type == "llm":
                types.add(worker_name)
        return Result.succ(list(types))

    except Exception as e:
        return Result.failed(code="E000X", msg=f"controller model types error {e}")


@router.get("/v1/model/supports")
async def model_supports(worker_manager: WorkerManager = Depends(get_worker_manager)):
    logger.info(f"/controller/model/supports")
    try:
        models = await worker_manager.supported_models()
        return Result.succ(FlatSupportedModel.from_supports(models))
    except Exception as e:
        return Result.failed(code="E000X", msg=f"Fetch supportd models error {e}")


async def no_stream_generator(chat):
    with root_tracer.start_span("no_stream_generator"):
        msg = await chat.nostream_call()
        yield f"data: {msg}\n\n"


async def stream_generator(chat, incremental: bool, model_name: str):
    """Generate streaming responses

    Our goal is to generate an openai-compatible streaming responses.
    Currently, the incremental response is compatible, and the full response will be transformed in the future.

    Args:
        chat (BaseChat): Chat instance.
        incremental (bool): Used to control whether the content is returned incrementally or in full each time.
        model_name (str): The model name

    Yields:
        _type_: streaming responses
    """
    span = root_tracer.start_span("stream_generator")
    msg = "[LLM_ERROR]: llm server has no output, maybe your prompt template is wrong."

    previous_response = ""
    async for chunk in chat.stream_call():
        if chunk:
            msg = chunk.replace("\ufffd", "")
            if incremental:
                incremental_output = msg[len(previous_response) :]
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant", content=incremental_output),
                )
                chunk = ChatCompletionStreamResponse(
                    id=chat.chat_session_id, choices=[choice_data], model=model_name
                )
                yield f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"
            else:
                # TODO generate an openai-compatible streaming responses
                msg = msg.replace("\n", "\\n")
                yield f"data:{msg}\n\n"
            previous_response = msg
            await asyncio.sleep(0.02)
    if incremental:
        yield "data: [DONE]\n\n"
    span.end()


def message2Vo(message: dict, order, model_name) -> MessageVo:
    return MessageVo(
        role=message["type"],
        context=message["data"]["content"],
        order=order,
        model_name=model_name,
    )
