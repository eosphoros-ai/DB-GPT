import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, status
from fastapi.security import HTTPBearer
from fastchat.protocol.api_protocol import (
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatMessage,
    UsageInfo,
)
from starlette.responses import StreamingResponse

from dbgpt.app.openapi.api_v1.api_v1 import (
    CHAT_FACTORY,
    __new_conversation,
    get_chat_instance,
    get_executor,
    no_stream_generator,
    stream_generator,
)
from dbgpt.app.openapi.api_v1.links.conv_links import ConvLinksDao
from dbgpt.app.openapi.api_v1.links.settings import SettingsDao
from dbgpt.app.openapi.api_view_model import (
    APIToken,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    ChatType,
    ConversationVo,
    DeltaMessage,
    LinksChatCompletionRequest,
    LinksChatExtraResponse,
    OpenAPIChatCompletionRequest,
)
from dbgpt.app.scene import BaseChat
from dbgpt.core.awel import logger
from dbgpt.serve.agent.db.gpts_app import adapt_native_app_model
from dbgpt.serve.agent.model import NativeTeamContext
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import SpanType, root_tracer

router = APIRouter()

token_auth_scheme = HTTPBearer()
conv_links_dao = ConvLinksDao()
settings_dao = SettingsDao()
LINKS_DBA_APP = "LINKS_DBA_APP"


class OpenAPIException(Exception):
    def __init__(
        self, message, type, param=None, code=None, status_code=400, http_resp=None
    ):
        if http_resp:
            self.status = http_resp.status
            self.reason = http_resp.reason
            self.body = http_resp.data
            self.headers = http_resp.getheaders()
        else:
            self.status = status_code
            self.reason = message
            self.body = {
                "error": {
                    "message": message,
                    "type": type,
                    "param": param,
                    "code": code,
                }
            }
            self.headers = None
        super().__init__(self.reason)

    def to_dict(self):
        return self.body


def check_api_key(
    api_key: str = Header(None, alias="DBGPT_API_KEY"),
    api_token: str = Header(None, alias="DBGPT_API_TOKEN"),
):
    """check api key and token
    Args:
        api_key: app code
        api_token: api token
    Return:
        APIToken
    Raise:
        OpenAPIException
    """
    token = None
    if api_key and api_token:
        token_dao = GptsPermissionDao()
        token = token_dao.get(api_key, api_token)

    if api_key is None or api_token is None or token is None:
        raise OpenAPIException(
            message="Invalid API key or token.",
            type="invalid_request_error",
            code=status.HTTP_401_UNAUTHORIZED,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    return APIToken(api_key=api_key, api_token=api_token, user_id=token.user_id)


def check_sse_api_key(
    api_key: str = Header(None, alias="APP-NAME"),
    api_token: str = Header(None, alias="API-TOKEN"),
    emp_id: Optional[str] = Header(None, alias="EMP-ID"),
):
    """check sse api key and token
    Args:
        api_key: app code
        api_token: api token
        emp_id: emp id
    Return:
        APIToken
    Raise:
        OpenAPIException
    """
    token = check_api_key(api_key, api_token)
    token.user_id = emp_id
    return token


@router.post("/v1/chat/completions")
async def chat_completions(
    request: OpenAPIChatCompletionRequest = OpenAPIChatCompletionRequest(),
    token: APIToken = Depends(check_api_key),
):
    """check api key and token
    Args:
        request: OpenAPIChatCompletionRequest
        token: APIToken
    Raise:
        OpenAPIException
    """
    logger.info(
        f"chat_completions:{request}，begin:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, timestamp={int(time.time() * 1000)}"
    )
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    if request.conv_uid is None:
        request.conv_uid = str(uuid.uuid1())
    context = request.context
    if request.chat_type == ChatType.APP.value:
        from dbgpt.serve.agent.agents.controller import multi_agents

        app_info = multi_agents.get_app(app_code=context["app_code"])
        if context.get("app_code") is None or app_info is None:
            raise OpenAPIException(
                message="Invalid app code",
                type="invalid_app_code_error",
                code=status.HTTP_400_BAD_REQUEST,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if app_info.team_mode == "native_app":
            native_context: NativeTeamContext = app_info.team_context
            dialogue = ConversationVo(
                conv_uid=request.conv_uid,
                user_input=request.user_input,
                app_code=context["app_code"],
                model=context.get("model", None),
                space=context.get("space", None),
                chat_mode=native_context.chat_scene,
            )
            dialogue = adapt_native_app_model(dialogue)
            request.chat_type = dialogue.chat_mode
            chat: BaseChat = await get_chat_instance(
                request, token, dialogue.select_param
            )
            if not chat.prompt_template.stream_out:
                return StreamingResponse(
                    no_stream_generator(chat),
                    headers=headers,
                    media_type="text/event-stream",
                )
            else:
                return StreamingResponse(
                    chat_knowledge(request, chat, True, context.get("model", None)),
                    headers=headers,
                    media_type="text/plain",
                )
        if request.stream:
            return StreamingResponse(
                chat_app(
                    request=request,
                    token=token,
                ),
                headers=headers,
                media_type="text/event-stream",
            )
        else:
            return await chat_app_no_stream(
                request=request,
                token=token,
            )
    elif request.chat_type == ChatType.KNOWLEDGE.value:
        with root_tracer.start_span(
            "get_chat_instance", span_type=SpanType.CHAT, metadata=request.dict()
        ):
            chat: BaseChat = await get_chat_instance(request, token)
        if context.get("space") is None:
            raise OpenAPIException(
                message="Invalid knowledge code",
                type="invalid_knowledge_code_error",
                code=status.HTTP_400_BAD_REQUEST,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        if not chat.prompt_template.stream_out:
            return StreamingResponse(
                no_stream_generator(chat),
                headers=headers,
                media_type="text/event-stream",
            )
        else:
            return StreamingResponse(
                chat_knowledge(request, chat, True, context.get("model", None)),
                headers=headers,
                media_type="text/plain",
            )
    elif request.chat_type == ChatType.NORMAL.value:
        request.chat_type = "chat_normal"
        chat: BaseChat = await get_chat_instance(request, token)
        if request.stream:
            return StreamingResponse(
                stream_generator(chat, request.stream, context.get("model")),
                headers=headers,
                media_type="text/plain",
            )
        else:
            return await no_stream_wrapper(request, chat)
    else:
        raise OpenAPIException(
            message="Invalid chat_type",
            type="invalid_chat_type_error",
            code=status.HTTP_400_BAD_REQUEST,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


# 对接研发小蜜
@router.post("/gpt/qa/sse")
async def qa_sse(
    request: LinksChatCompletionRequest = LinksChatCompletionRequest(),
    token: APIToken = Depends(check_sse_api_key),
):
    """check api key and token
    Args:
        request: OpenAPIChatCompletionRequest
    Raise:
        OpenAPIException
    """
    logger.info(
        f"chat_completions:{request}，begin:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, timestamp={int(time.time() * 1000)}"
    )
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    if request.conversation_id is None:
        request.conversation_id = str(uuid.uuid1())
    setting = settings_dao.get_one({"setting_key": LINKS_DBA_APP})
    if not setting and setting.setting_value:
        raise OpenAPIException(
            message="Invalid app code",
            type="invalid_app_code_error",
            code=status.HTTP_400_BAD_REQUEST,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    app_id = setting.setting_value
    from dbgpt.serve.agent.agents.controller import multi_agents

    app_code = multi_agents.get_app(app_code=app_id)
    if app_code is None:
        raise OpenAPIException(
            message="Invalid app code",
            type="invalid_app_code_error",
            code=status.HTTP_400_BAD_REQUEST,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    return StreamingResponse(
        chat_app_links_sse(request=request, token=token, app_code=app_id),
        headers=headers,
        media_type="text/event-stream",
    )


async def chat_app(
    request: OpenAPIChatCompletionRequest = None, token: APIToken = None
):
    """chat app stream
    Args:
        request (OpenAPIChatCompletionRequest): request
        token (APIToken): token
    """
    try:
        context = request.context
        from dbgpt.serve.agent.agents.controller import multi_agents

        async for output in multi_agents.app_agent_chat(
            conv_uid=request.conv_uid,
            gpts_name=context["app_code"],
            user_query=request.user_input,
            user_code=token.user_id,
            sys_code=token.api_key,
            enable_verbose=context.get("enable_verbose"),
            stream=request.stream,
            **context.get("ext_info", {}),
        ):
            if context.get("enable_verbose"):
                logger.info(f"[DEBUG DF yield BEGIN]:{output}")
                yield output
                logger.info(f"[DEBUG DF yield END]")
            else:
                model = context.get("model", None)
                role = "assistant"
                content = output
                if isinstance(output, dict):
                    content = output["markdown"]
                    role = output["sender"]
                    model = output["model"]
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(role=role, content=content),
                )
                chunk = ChatCompletionStreamResponse(
                    id=request.conv_uid,
                    choices=[choice_data],
                    model=model,
                    created=int(time.time()),
                )
                content = f"data: {json.dumps(chunk.dict(exclude_unset=True), ensure_ascii=False)}\n\n"
                yield content
        yield "data:[DONE]"
        logger.info(
            f"chat_completions end:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
    except Exception as ex:
        logger.exception(f"chat app exception: {ex}")
        yield f"Error: {str(ex)}"


async def chat_app_links_sse(
    request: LinksChatCompletionRequest = None,
    token: APIToken = None,
    app_code: str = None,
):
    """chat app stream
    Args:
        request (OpenAPIChatCompletionRequest): request
        token (APIToken): token
        app_code (str): app_code
    """
    try:
        model = None
        begin_event = False
        from dbgpt.serve.agent.agents.controller import multi_agents

        previous_output = ""
        async for output in multi_agents.app_agent_chat(
            conv_uid=request.conversation_id,
            gpts_name=app_code,
            user_query=request.query,
            user_code=token.user_id,
            sys_code=token.api_key,
            enable_verbose=False,
            stream=True,
        ):
            content = output
            increment = ""
            if isinstance(output, dict):
                content = output["markdown"]
                model = output["model"]
                current_output = content
                increment = current_output[len(previous_output) :]
                previous_output = current_output
            chunk = {"text": increment}
            content = f"data:{json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield f"event:body\n\n"
            yield content
        extra = LinksChatExtraResponse(gptModel=model, scriptLinks=[])
        yield f"event:extra\n\n"
        yield f"data:{json.dumps(extra.dict(exclude_unset=True), ensure_ascii=False)}\n\n"
        links_filters = request.filters
        conv_links_dao.create(
            {
                "conv_id": request.conversation_id,
                "message_id": request.message_id,
                "chat_room_id": links_filters.chatRoomId if links_filters else None,
                "app_code": app_code,
                "emp_id": token.user_id,
            }
        )
        logger.info(f"links sse end:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as ex:
        logger.exception(f"chat app exception: {ex}")
        yield f"Error: {str(ex)}"


async def chat_app_no_stream(
    request: OpenAPIChatCompletionRequest = None, token: APIToken = None
) -> ChatCompletionResponse:
    """chat app no stream

    Args:
        request (OpenAPIChatCompletionRequest): request
        token (APIToken): token
    Returns:
        ChatCompletionResponse
    """
    try:
        context = request.context
        from dbgpt.serve.agent.agents.controller import multi_agents

        async for output in multi_agents.app_agent_chat(
            conv_uid=request.conv_uid,
            gpts_name=context["app_code"],
            user_query=request.user_input,
            user_code=token.user_id,
            sys_code=token.api_key,
            enable_verbose=context.get("enable_verbose"),
            stream=request.stream,
            **context.get("ext_info", {}),
        ):
            model = context.get("model", None)
            role = "assistant"
            content = output
            if isinstance(output, dict):
                content = output["markdown"]
                role = output["sender"]
                model = output["model"]

            choice_data = ChatCompletionResponseChoice(
                index=0,
                message=ChatMessage(role=role, content=content),
            )
            usage = UsageInfo()
            response = ChatCompletionResponse(
                id=request.conv_uid,
                choices=[choice_data],
                model=model if model is not None else "?",
                usage=usage,
            )
            return response.dict()
    except Exception as ex:
        logger.info(f"chat_app_no_stream exception: {ex}")
        return ChatCompletionResponse()


async def chat_knowledge(
    request: OpenAPIChatCompletionRequest = None,
    chat: BaseChat = None,
    incremental: bool = None,
    model_name: str = None,
):
    """chat knowledge stream
    Args:
        chat (BaseChat): Chat instance.
        incremental (bool): Used to control whether the content
        is returned incrementally or in full each time.
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
                msg = msg.replace("\n", "\\n")
                incremental_output = msg[len(previous_response) :]
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant", content=incremental_output),
                )
                chunk = ChatCompletionStreamResponse(
                    id=request.conv_uid,
                    choices=[choice_data],
                    model=model_name,
                    created=int(time.time()),
                )
                content = f"data: {json.dumps(chunk.dict(exclude_unset=True), ensure_ascii=False)}\n\n"
                yield content
            else:
                msg = msg.replace("\n", "\\n")
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant", content=msg),
                )
                chunk = ChatCompletionStreamResponse(
                    id=request.conv_uid,
                    choices=[choice_data],
                    model=model_name,
                    created=int(time.time()),
                )
                content = (
                    f"data: {chunk.json(exclude_unset=True, ensure_ascii=False)}\n\n"
                )
                yield content
            previous_response = msg
    if incremental:
        yield "data: [DONE]\n\n"
    span.end()


async def no_stream_wrapper(
    request: OpenAPIChatCompletionRequest, chat: BaseChat
) -> ChatCompletionResponse:
    """
    no stream wrapper
    Args:
        request (OpenAPIChatCompletionRequest): request
        chat (BaseChat): chat
    """
    with root_tracer.start_span("no_stream_generator"):
        response = await chat.nostream_call()
        msg = response.replace("\ufffd", "").replace("&quot;", '"')
        choice_data = ChatCompletionResponseChoice(
            index=0,
            message=ChatMessage(role="assistant", content=msg),
        )
        usage = UsageInfo()
        model = request.context.get("model", None)
        return ChatCompletionResponse(
            id=request.conv_uid, choices=[choice_data], model=model, usage=usage
        )


async def get_chat_instance(
    dialogue: OpenAPIChatCompletionRequest = Body(),
    token: APIToken = None,
    select_param: Optional[str] = None,
) -> BaseChat:
    logger.info(f"get_chat_instance:{dialogue}")
    if not dialogue.conv_uid:
        conv_vo = __new_conversation(dialogue.chat_type, token.user_id, token.api_key)
        dialogue.conv_uid = conv_vo.conv_uid

    context = dialogue.context
    select_param = select_param if select_param else context.get("space")
    chat_param = {
        "chat_session_id": dialogue.conv_uid,
        "user_name": token.user_id,
        "sys_code": token.api_key,
        "current_user_input": dialogue.user_input,
        "select_param": select_param,
        "model_name": context["model"],
        "temperature": context.get("temperature", None),
    }
    chat: BaseChat = await blocking_func_to_async(
        get_executor(),
        CHAT_FACTORY.get_implementation,
        dialogue.chat_type,
        **{"chat_param": chat_param},
    )
    return chat
