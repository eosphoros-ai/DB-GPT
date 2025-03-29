import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List

from dbgpt.core import (
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatCompletionResponseStreamChoice,
    ChatCompletionStreamResponse,
    ChatMessage,
    DeltaMessage,
    ModelMessage,
    ModelMessageRole,
)
from dbgpt.model.parameter import ModelParameters

logger = logging.getLogger(__name__)


async def generate_stream(
    model: Any,
    tokenizer: Any,
    params: Dict[str, Any],
    model_messages: List[ModelMessage],
    model_parameters: ModelParameters,
) -> AsyncIterator[ChatCompletionStreamResponse]:
    """Generate stream response using SGLang."""
    try:
        import sglang as sgl
    except ImportError:
        raise ImportError("Please install sglang first: pip install sglang")

    # Message format convert
    messages = []
    for msg in model_messages:
        role = msg.role
        if role == ModelMessageRole.HUMAN:
            role = "user"
        elif role == ModelMessageRole.SYSTEM:
            role = "system"
        elif role == ModelMessageRole.AI:
            role = "assistant"
        else:
            role = "user"

        messages.append({"role": role, "content": msg.content})

    # Model params set
    temperature = model_parameters.temperature
    top_p = model_parameters.top_p
    max_tokens = model_parameters.max_new_tokens

    # Create SGLang request
    async def stream_generator():
        # Use SGLang async API generate
        state = sgl.RuntimeState()

        @sgl.function
        def chat(state, messages):
            sgl.gen(
                messages=messages,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )

        # Start task generate
        task = model.submit_task(chat, state, messages)

        # Fetch result
        generated_text = ""
        async for output in task.stream_output():
            if hasattr(output, "text"):
                new_text = output.text
                delta = new_text[len(generated_text) :]
                generated_text = new_text

                # Create Stream reponse
                choice = ChatCompletionResponseStreamChoice(
                    index=0,
                    delta=DeltaMessage(role="assistant", content=delta),
                    finish_reason=None,
                )
                chunk = ChatCompletionStreamResponse(
                    id=params.get("id", "chatcmpl-default"),
                    model=params.get("model", "sglang-model"),
                    choices=[choice],
                    created=int(asyncio.get_event_loop().time()),
                )
                yield chunk

        # Send complete signal
        choice = ChatCompletionResponseStreamChoice(
            index=0,
            delta=DeltaMessage(role="assistant", content=""),
            finish_reason="stop",
        )
        chunk = ChatCompletionStreamResponse(
            id=params.get("id", "chatcmpl-default"),
            model=params.get("model", "sglang-model"),
            choices=[choice],
            created=int(asyncio.get_event_loop().time()),
        )
        yield chunk

    async for chunk in stream_generator():
        yield chunk


async def generate(
    model: Any,
    tokenizer: Any,
    params: Dict[str, Any],
    model_messages: List[ModelMessage],
    model_parameters: ModelParameters,
) -> ChatCompletionResponse:
    """Generate completion using SGLang."""
    try:
        import sglang as sgl
    except ImportError:
        raise ImportError("Please install sglang first: pip install sglang")

    # Convert format to SGlang
    messages = []
    for msg in model_messages:
        role = msg.role
        if role == ModelMessageRole.HUMAN:
            role = "user"
        elif role == ModelMessageRole.SYSTEM:
            role = "system"
        elif role == ModelMessageRole.AI:
            role = "assistant"
        else:
            role = "user"

        messages.append({"role": role, "content": msg.content})

    temperature = model_parameters.temperature
    top_p = model_parameters.top_p
    max_tokens = model_parameters.max_new_tokens

    state = sgl.RuntimeState()

    @sgl.function
    def chat(state, messages):
        sgl.gen(
            messages=messages,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

    task = await model.submit_task(chat, state, messages)
    result = await task.wait()

    choice = ChatCompletionResponseChoice(
        index=0,
        message=ChatMessage(role="assistant", content=result.text),
        finish_reason="stop",
    )

    response = ChatCompletionResponse(
        id=params.get("id", "chatcmpl-default"),
        model=params.get("model", "sglang-model"),
        choices=[choice],
        created=int(asyncio.get_event_loop().time()),
    )

    return response
