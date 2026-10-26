import json
import re
import time
import uuid
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse, StreamingResponse

from dbgpt._private.pydantic import model_to_dict, model_to_json
from dbgpt.component import SystemApp, logger
from dbgpt.core.schema.api import (
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    DeltaMessage,
    ErrorResponse,
    UsageInfo,
)
from dbgpt.model.cluster.apiserver.api import APISettings
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import SpanType, root_tracer
from dbgpt_app.openapi.api_v1.api_v1 import (
    CHAT_FACTORY,
    __new_conversation,
    get_chat_flow,
    get_executor,
    stream_generator,
)
from dbgpt_app.scene import BaseChat, ChatParam, ChatScene
from dbgpt_client.schema import ChatCompletionRequestBody, ChatMode
from dbgpt_serve.agent.agents.controller import multi_agents
from dbgpt_serve.flow.api.endpoints import get_service

router = APIRouter()
api_settings = APISettings()
get_bearer_token = HTTPBearer(auto_error=False)


async def check_api_key(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(get_bearer_token),
    service=Depends(get_service),
) -> Optional[str]:
    """Check the api key
    Args:
        auth (Optional[HTTPAuthorizationCredentials]): The bearer token.
        service (Service): The flow service.
    """
    if service.config.api_keys:
        api_keys = [key.strip() for key in service.config.api_keys.split(",")]
        if auth is None or (token := auth.credentials) not in api_keys:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "message": "",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_api_key",
                    }
                },
            )
        return token
    else:
        return None


# OpenAI-compat alias for external harness engines (e.g.
# pi): they hit ``<baseUrl>/chat/completions`` and their
# OpenAI client insists on a ``/v1`` suffix.
@router.post("/v2/v1/chat/completions", dependencies=[Depends(check_api_key)])
@router.post("/v2/chat/completions", dependencies=[Depends(check_api_key)])
async def chat_completions(
    request: ChatCompletionRequestBody = Body(),
    service=Depends(get_service),
):
    """Chat V2 completions
    Args:
        request (ChatCompletionRequestBody): The chat request.
        service (FlowService): The flow service.
    Raises:
        HTTPException: If the request is invalid.
    """
    logger.info(
        f"chat_completions:{request.chat_mode},{request.chat_param},{request.model}"
    )
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    # check chat request
    check_chat_request(request)
    if request.conv_uid is None:
        request.conv_uid = str(uuid.uuid4())
    if request.chat_mode == ChatMode.CHAT_APP.value:
        if request.stream is False:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "message": "chat app now not support no stream",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_request_error",
                    }
                },
            )
        return StreamingResponse(
            chat_app_stream_wrapper(
                request=request,
            ),
            headers=headers,
            media_type="text/event-stream",
        )
    elif request.chat_mode == ChatMode.CHAT_AWEL_FLOW.value:
        if not request.stream:
            return await chat_flow_wrapper(request)
        else:
            return StreamingResponse(
                chat_flow_stream_wrapper(request),
                headers=headers,
                media_type="text/event-stream",
            )
    elif (
        request.chat_mode is None
        or request.chat_mode == ChatMode.CHAT_NORMAL.value
        or request.chat_mode == ChatMode.CHAT_KNOWLEDGE.value
        or request.chat_mode == ChatMode.CHAT_DATA.value
        or request.chat_mode == ChatMode.CHAT_DB_QA.value
        or request.chat_mode == ChatMode.CHAT_DASHBOARD.value
    ):
        with root_tracer.start_span(
            "get_chat_instance",
            span_type=SpanType.CHAT,
            metadata=model_to_dict(request),
        ):
            chat: BaseChat = await get_chat_instance(request, service.system_app)

        if not request.stream:
            # TODO: Adapt to the new chat interface
            return await no_stream_wrapper(request, chat)
        else:
            return StreamingResponse(
                stream_generator(
                    chat,
                    request.incremental,
                    request.model,
                    text_output=False,
                    openai_format=True,
                ),
                headers=headers,
                media_type="text/event-stream",
            )
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "chat mode now only support chat_normal, chat_app, "
                    "chat_flow, chat_knowledge, chat_data, chat_dashboard",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_chat_mode",
                }
            },
        )


async def get_chat_instance(
    dialogue: ChatCompletionRequestBody = Body(), system_app: SystemApp = None
) -> BaseChat:
    """
    Get chat instance
    Args:
        dialogue (OpenAPIChatCompletionRequest): The chat request.
        system_app (SystemApp): system app.
    """
    logger.info(f"get_chat_instance:{dialogue}")
    if not dialogue.chat_mode:
        dialogue.chat_mode = ChatScene.ChatNormal.value()
    if not dialogue.conv_uid:
        conv_vo = __new_conversation(
            dialogue.chat_mode, dialogue.user_name, dialogue.sys_code
        )
        dialogue.conv_uid = conv_vo.conv_uid
    if dialogue.chat_mode == "chat_data":
        dialogue.chat_mode = ChatScene.ChatWithDbExecute.value()
    if not ChatScene.is_valid_mode(dialogue.chat_mode):
        raise StopAsyncIteration(f"Unsupported Chat Mode,{dialogue.chat_mode}!")

    chat_param = ChatParam(
        chat_session_id=dialogue.conv_uid,
        user_name=dialogue.user_name,
        sys_code=dialogue.sys_code,
        current_user_input=dialogue.single_prompt(),
        select_param=dialogue.chat_param,
        model_name=dialogue.model,
        temperature=dialogue.temperature,
        max_new_tokens=dialogue.max_new_tokens,
        chat_mode=ChatScene.of_mode(dialogue.chat_mode),
    )
    chat: BaseChat = await blocking_func_to_async(
        get_executor(),
        CHAT_FACTORY.get_implementation,
        dialogue.chat_mode,
        system_app,
        **{"chat_param": chat_param},
    )
    return chat


async def no_stream_wrapper(
    request: ChatCompletionRequestBody, chat: BaseChat
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
        return ChatCompletionResponse(
            id=request.conv_uid, choices=[choice_data], model=request.model, usage=usage
        )


async def chat_app_stream_wrapper(request: ChatCompletionRequestBody = None):
    """chat app stream
    Args:
        request (OpenAPIChatCompletionRequest): request
        token (APIToken): token
    """
    async for output in multi_agents.app_agent_chat(
        conv_uid=request.conv_uid,
        gpts_name=request.chat_param,
        user_query=request.single_prompt(),
        user_code=request.user_name,
        sys_code=request.sys_code,
    ):
        match = re.search(r"data:\s*({.*})", output)
        if match:
            json_str = match.group(1)
            vis = json.loads(json_str)
            vis_content = vis.get("vis", None)
            if vis_content != "[DONE]":
                choice_data = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant", content=vis.get("vis", None)),
                )
                chunk = ChatCompletionStreamResponse(
                    id=request.conv_uid,
                    choices=[choice_data],
                    model=request.model,
                    created=int(time.time()),
                )
                json_content = model_to_json(
                    chunk, exclude_unset=True, ensure_ascii=False
                )
                content = f"data: {json_content}\n\n"
                yield content
    yield "data: [DONE]\n\n"


async def chat_flow_wrapper(request: ChatCompletionRequestBody):
    flow_service = get_chat_flow()
    flow_req = request.to_common_llm_http_request_body()
    flow_uid = request.chat_param
    output = await flow_service.safe_chat_flow(flow_uid, flow_req)
    if not output.success:
        return JSONResponse(
            model_to_dict(ErrorResponse(message=output.text, code=output.error_code)),
            status_code=400,
        )
    else:
        choice_data = ChatCompletionResponseChoice(
            index=0,
            message=ChatMessage(
                role="assistant",
                content=output.text,
                reasoning_content=output.thinking_text,
            ),
        )
        if output.usage:
            usage = UsageInfo(**output.usage)
        else:
            usage = UsageInfo()
        return ChatCompletionResponse(
            id=request.conv_uid, choices=[choice_data], model=request.model, usage=usage
        )


async def chat_flow_stream_wrapper(
    request: ChatCompletionRequestBody,
) -> AsyncIterator[str]:
    """chat app stream
    Args:
        request (OpenAPIChatCompletionRequest): request
    """
    flow_service = get_chat_flow()
    flow_req = request.to_common_llm_http_request_body()
    flow_uid = request.chat_param

    async for output in flow_service.chat_stream_openai(flow_uid, flow_req):
        yield output


def check_chat_request(request: ChatCompletionRequestBody = Body()):
    """
    Check the chat request
    Args:
        request (ChatCompletionRequestBody): The chat request.
    Raises:
        HTTPException: If the request is invalid.
    """
    if request.chat_mode and request.chat_mode != ChatScene.ChatNormal.value():
        if request.chat_param is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "message": "chat param is None",
                        "type": "invalid_request_error",
                        "param": None,
                        "code": "invalid_chat_param",
                    }
                },
            )
    if request.model is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "model is None",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_model",
                }
            },
        )
    if request.messages is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "message": "messages is None",
                    "type": "invalid_request_error",
                    "param": None,
                    "code": "invalid_messages",
                }
            },
        )


# ── Agentic chat completions (tools passthrough) ──────────────────────────
#
# Purpose-built OpenAI-compatible endpoint for external harness engines
# (pi, DSH): accepts the standard request shape including ``tools`` and
# ``tool_choice``, forwards them to the LLM untouched, and returns
# OpenAI-shaped responses (non-stream JSON or SSE chunks with
# ``tool_calls``). The legacy /v2 chat path routes through BaseChat's
# scene machinery and does not carry tool schemas.


def _agentic_message_content(content) -> str:
    """Collapse OpenAI content blocks into a plain string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(str(block.get("text", "")))
                elif block.get("type") == "thinking":
                    parts.append(str(block.get("thinking", "")))
        return "\n".join(p for p in parts if p)
    return "" if content is None else str(content)


def _agentic_to_model_messages(messages: list) -> list:
    """Convert OpenAI chat messages to ModelMessage (roles mapped)."""
    from dbgpt.core.interface.llm import ModelMessage

    out = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role") or "user"
        mapped = {
            "user": "human",
            "assistant": "ai",
            "system": "system",
            "tool": "tool",
        }.get(role, role)
        out.append(
            ModelMessage(
                role=mapped,
                content=_agentic_message_content(msg.get("content")),
                tool_calls=msg.get("tool_calls"),
                tool_call_id=msg.get("tool_call_id"),
            )
        )
    return out


def _agentic_usage(out) -> dict:
    usage = getattr(out, "usage", None) or {}
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def _agentic_out_text(content) -> str:
    """Extract plain text from ModelOutput.content.

    ModelOutput.content is ``Union[MediaContent, List[MediaContent]]`` —
    a dataclass, not JSON-serializable. Pull the text payload out of
    its ``object.data`` so SSE frames stay plain JSON.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_agentic_out_text(c) for c in content)
    # MediaContent dataclass: .object.data holds the payload
    obj = getattr(content, "object", None)
    data = getattr(obj, "data", None) if obj is not None else None
    if isinstance(data, str):
        return data
    if data is not None:
        return str(data)
    return str(content)


@router.post("/v2/agentic/chat/completions", dependencies=[Depends(check_api_key)])
@router.post("/v2/v1/agentic/chat/completions", dependencies=[Depends(check_api_key)])
async def agentic_chat_completions(
    payload: dict = Body(),
    service=Depends(get_service),
):
    """OpenAI-compatible chat completions with native tools passthrough."""
    import time as _time

    from dbgpt.component import ComponentType
    from dbgpt.core.interface.llm import ModelRequest, ModelRequestContext
    from dbgpt.model.cluster import WorkerManagerFactory
    from dbgpt.model.cluster.client import DefaultLLMClient

    model = payload.get("model")
    messages = payload.get("messages") or []
    if not model:
        raise HTTPException(
            status_code=400, detail={"error": {"message": "model is required"}}
        )
    if not messages:
        raise HTTPException(
            status_code=400, detail={"error": {"message": "messages is required"}}
        )

    stream = bool(payload.get("stream"))
    request = ModelRequest(
        model=model,
        messages=_agentic_to_model_messages(messages),
        temperature=payload.get("temperature"),
        max_new_tokens=payload.get("max_tokens"),
        stop=payload.get("stop"),
        tools=payload.get("tools"),
        tool_choice=payload.get("tool_choice"),
        context=ModelRequestContext(stream=stream),
    )

    llm_client = DefaultLLMClient(
        service.system_app.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create(),
        auto_convert_message=True,
    )

    if not stream:
        out = await llm_client.generate(request)
        if getattr(out, "error_code", 0):
            raise HTTPException(
                status_code=500,
                detail={"error": {"message": str(getattr(out, "text", out))}},
            )
        return {
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(_time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": _agentic_out_text(out.content),
                        **({"tool_calls": out.tool_calls} if out.tool_calls else {}),
                    },
                    "finish_reason": (out.finish_reason or "stop"),
                }
            ],
            "usage": _agentic_usage(out),
        }

    async def _chunks():
        chat_id = f"chatcmpl-{uuid.uuid4()}"
        created = int(_time.time())
        # Worker-stream ModelOutput carries CUMULATIVE text/tool_calls;
        # OpenAI stream chunks must carry incremental deltas, so diff here.
        prev_text = ""
        prev_tool_args: dict = {}
        seen_tool_names: set = set()
        async for out in llm_client.generate_stream(request):
            if getattr(out, "error_code", 0):
                err_msg = str(getattr(out, "text", out))
                yield f"data: {json.dumps({'error': {'message': err_msg}})}\n\n"
                break
            delta: dict = {"role": "assistant"}
            full_text = _agentic_out_text(out.content)
            if full_text.startswith(prev_text):
                inc_text = full_text[len(prev_text) :]
            else:
                inc_text = full_text
            prev_text = full_text
            if inc_text:
                delta["content"] = inc_text
            tool_frags = []
            for tc_idx, tc in enumerate(getattr(out, "tool_calls", None) or []):
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function") or {}
                tc_name = fn.get("name") or ""
                tc_args = fn.get("arguments") or ""
                if not isinstance(tc_args, str):
                    tc_args = json.dumps(tc_args, ensure_ascii=False)
                p_args = prev_tool_args.get(tc_idx, "")
                if tc_args.startswith(p_args):
                    inc_args = tc_args[len(p_args) :]
                else:
                    inc_args = tc_args
                prev_tool_args[tc_idx] = tc_args
                if inc_args or (tc_name and tc_idx not in seen_tool_names):
                    if tc_name:
                        seen_tool_names.add(tc_idx)
                    tool_frags.append(
                        {
                            "index": tc_idx,
                            "id": tc.get("id"),
                            "type": "function",
                            "function": {"name": tc_name, "arguments": inc_args},
                        }
                    )
            if tool_frags:
                delta["tool_calls"] = tool_frags
            chunk = {
                "id": chat_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": delta,
                        "finish_reason": out.finish_reason or None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False, default=str)}\n\n"
        # OpenAI spec: a terminal chunk with an empty delta and a
        # finish_reason closes the message; clients (pi included) rely on
        # finish_reason="tool_calls" to finalize streamed tool calls.
        final_reason = "tool_calls" if (prev_tool_args or seen_tool_names) else "stop"
        final_chunk = {
            "id": chat_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": final_reason}],
        }
        yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _chunks(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
