"""The utility functions for chatting with the DAG task."""

import json
import traceback
from typing import Any, AsyncIterator, Dict, Optional

from ...interface.llm import ModelInferenceMetrics, ModelOutput
from ...schema.api import ChatCompletionResponseStreamChoice
from ..operators.base import BaseOperator
from ..trigger.http_trigger import CommonLLMHttpResponseBody


def is_chat_flow_type(output_obj: Any, is_class: bool = False) -> bool:
    """Check whether the output object is a chat flow type."""
    if is_class:
        return output_obj in (str, CommonLLMHttpResponseBody, ModelOutput)
    else:
        chat_types = (str, CommonLLMHttpResponseBody)
        return isinstance(output_obj, chat_types)


def is_agent_flow_type(output_obj: Any, is_class: bool = False) -> bool:
    """Check whether the output object is a agent flow type."""
    if is_class:
        return output_obj in (str, CommonLLMHttpResponseBody, ModelOutput)
    else:
        chat_types = (str, CommonLLMHttpResponseBody)
        return isinstance(output_obj, chat_types)


async def safe_chat_with_dag_task(
    task: BaseOperator, request: Any, covert_to_str: bool = False
) -> ModelOutput:
    """Chat with the DAG task.

    Args:
        task (BaseOperator): The DAG task to be executed.
        request (Any): The request to be passed to the DAG task.
        covert_to_str (bool, optional): Whether to convert the output to string.

    Returns:
        ModelOutput: The model output, the result is not incremental.
    """
    try:
        finish_reason = None
        usage = None
        metrics = None
        error_code = 0
        text = ""
        thinking_text = ""
        async for output in safe_chat_stream_with_dag_task(
            task, request, False, covert_to_str=covert_to_str
        ):
            finish_reason = output.finish_reason
            usage = output.usage
            metrics = output.metrics
            error_code = output.error_code
            if output.has_text:
                text = output.text
            if output.has_thinking:
                thinking_text = output.thinking_text
        return ModelOutput.build(
            text,
            thinking_text,
            error_code=error_code,
            metrics=metrics,
            usage=usage,
            finish_reason=finish_reason,
        )
    except Exception as e:
        return ModelOutput(error_code=1, text=str(e), incremental=False)


async def safe_chat_stream_with_dag_task(
    task: BaseOperator, request: Any, incremental: bool, covert_to_str: bool = False
) -> AsyncIterator[ModelOutput]:
    """Chat with the DAG task.

    This function is similar to `chat_stream_with_dag_task`, but it will catch the
    exception and return the error message.

    Args:
        task (BaseOperator): The DAG task to be executed.
        request (Any): The request to be passed to the DAG task.
        incremental (bool): Whether the output is incremental.
        covert_to_str (bool, optional): Whether to convert the output to string.

    Yields:
        ModelOutput: The model output.
    """
    try:
        async for output in chat_stream_with_dag_task(
            task, request, incremental, covert_to_str=covert_to_str
        ):
            yield output
    except Exception as e:
        simple_error_msg = str(e)
        if not simple_error_msg:
            simple_error_msg = traceback.format_exc()
        yield ModelOutput(error_code=1, text=simple_error_msg, incremental=incremental)
    finally:
        if task.streaming_operator and task.dag:
            await task.dag._after_dag_end(task.current_event_loop_task_id)


def _is_sse_output(task: BaseOperator) -> bool:
    """Check whether the DAG task is a server-sent event output.

    Args:
        task (BaseOperator): The DAG task.

    Returns:
        bool: Whether the DAG task is a server-sent event output.
    """
    return task.output_format is not None and task.output_format.upper() == "SSE"


async def chat_stream_with_dag_task(
    task: BaseOperator, request: Any, incremental: bool, covert_to_str: bool = False
) -> AsyncIterator[ModelOutput]:
    """Chat with the DAG task.

    Args:
        task (BaseOperator): The DAG task to be executed.
        request (Any): The request to be passed to the DAG task.
        incremental (bool): Whether the output is incremental.
        covert_to_str (bool, optional): Whether to convert the output to string.

    Yields:
        ModelOutput: The model output.
    """
    is_sse = _is_sse_output(task)
    if not task.streaming_operator:
        try:
            result = await task.call(request)
            model_output = parse_single_output(
                result, is_sse, covert_to_str=covert_to_str
            )
            model_output.incremental = incremental
            yield model_output
        except Exception as e:
            simple_error_msg = str(e)
            if not simple_error_msg:
                simple_error_msg = traceback.format_exc()
            yield ModelOutput(
                error_code=1, text=simple_error_msg, incremental=incremental
            )
    else:
        from dbgpt.model.utils.chatgpt_utils import OpenAIStreamingOutputOperator

        if OpenAIStreamingOutputOperator and isinstance(
            task, OpenAIStreamingOutputOperator
        ):
            full_text = ""
            full_thinking_text = ""
            async for output in await task.call_stream(request):
                model_output = parse_openai_output(output)
                # The output of the OpenAI streaming API is incremental
                if model_output.has_thinking:
                    full_thinking_text += model_output.thinking_text
                if model_output.has_text:
                    full_text += model_output.text
                model_output.incremental = incremental
                if not incremental:
                    model_output = ModelOutput.build(
                        full_text,
                        full_thinking_text,
                        error_code=model_output.error_code,
                        usage=model_output.usage,
                        finish_reason=model_output.finish_reason,
                    )
                yield model_output
                if not model_output.success:
                    break
        else:
            full_text = ""
            full_thinking_text = ""
            previous_text = ""
            previous_thinking_text = ""
            async for output in await task.call_stream(request):
                model_output = parse_single_output(
                    output, is_sse, covert_to_str=covert_to_str
                )
                model_output.incremental = incremental
                if task.incremental_output:
                    # Output is incremental, append the text
                    if model_output.has_thinking:
                        full_thinking_text += model_output.thinking_text
                    if model_output.has_text:
                        full_text += model_output.text
                else:
                    # Output is not incremental, last output is the full text
                    if model_output.has_thinking:
                        full_thinking_text = model_output.thinking_text

                    if model_output.has_text:
                        full_text = model_output.text
                if not incremental:
                    # Return the full text
                    model_output = ModelOutput.build(
                        full_text,
                        full_thinking_text,
                        error_code=model_output.error_code,
                        usage=model_output.usage,
                        finish_reason=model_output.finish_reason,
                    )
                else:
                    # Return the incremental text
                    delta_text = full_text[len(previous_text) :]
                    previous_text = (
                        full_text
                        if len(full_text) > len(previous_text)
                        else previous_text
                    )
                    delta_thinking_text = full_thinking_text[
                        len(previous_thinking_text) :
                    ]
                    previous_thinking_text = (
                        full_thinking_text
                        if len(full_thinking_text) > len(previous_thinking_text)
                        else previous_thinking_text
                    )
                    model_output = ModelOutput.build(
                        delta_text,
                        delta_thinking_text,
                        error_code=model_output.error_code,
                        usage=model_output.usage,
                        finish_reason=model_output.finish_reason,
                    )
                yield model_output
                if not model_output.success:
                    break


def parse_single_output(
    output: Any, is_sse: bool, covert_to_str: bool = False
) -> ModelOutput:
    """Parse the single output.

    Args:
        output (Any): The output to parse.
        is_sse (bool): Whether the output is in SSE format.
        covert_to_str (bool, optional): Whether to convert the output to string.
        Defaults to False.

    Returns:
        ModelOutput: The parsed output.
    """
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    metrics: Optional[ModelInferenceMetrics] = None

    if output is None:
        error_code = 1
        text = "The output is None!"
    elif isinstance(output, str):
        if is_sse:
            sse_output = parse_sse_data(output)
            if sse_output is None:
                error_code = 1
                text = "The output is not a SSE format"
            else:
                error_code = 0
                text = sse_output
        else:
            error_code = 0
            text = output
    elif isinstance(output, ModelOutput):
        # error_code = output.error_code
        # text = output.text
        # finish_reason = output.finish_reason
        # usage = output.usage
        # metrics = output.metrics
        return output
    elif isinstance(output, CommonLLMHttpResponseBody):
        error_code = output.error_code
        text = output.text
    elif isinstance(output, dict):
        error_code = 0
        text = json.dumps(output, ensure_ascii=False)
    elif covert_to_str:
        error_code = 0
        text = str(output)
    else:
        error_code = 1
        text = f"The output is not a valid format({type(output)})"
    return ModelOutput(
        error_code=error_code,
        text=text,
        finish_reason=finish_reason,
        usage=usage,
        metrics=metrics,
    )


def parse_openai_output(output: Any) -> ModelOutput:
    """Parse the OpenAI output.

    Args:
        output (Any): The output to parse. It must be a stream format.

    Returns:
        ModelOutput: The parsed output.
    """
    text = ""
    if not isinstance(output, str):
        return ModelOutput(
            error_code=1,
            text="The output is not a stream format",
        )
    if output.strip() == "data: [DONE]" or output.strip() == "data:[DONE]":
        return ModelOutput(error_code=0, text="")
    if not output.startswith("data:"):
        return ModelOutput(
            error_code=1,
            text="The output is not a stream format",
        )

    sse_output = parse_sse_data(output)
    if sse_output is None:
        return ModelOutput(error_code=1, text="The output is not a SSE format")
    json_data = sse_output.strip()
    try:
        dict_data = json.loads(json_data)
    except Exception as e:
        return ModelOutput(
            error_code=1,
            text=f"Invalid JSON data: {json_data}, {e}",
        )
    if "choices" not in dict_data:
        return ModelOutput(
            error_code=1,
            text=dict_data.get("text", "Unknown error"),
        )
    choices = dict_data["choices"]
    finish_reason: Optional[str] = None
    reasoning_content: Optional[str] = None
    if choices:
        choice = choices[0]
        delta_data = ChatCompletionResponseStreamChoice(**choice)
        if delta_data.delta.content:
            text = delta_data.delta.content
        if delta_data.delta.reasoning_content:
            reasoning_content = delta_data.delta.reasoning_content
        finish_reason = delta_data.finish_reason
    return ModelOutput.build(text, reasoning_content, finish_reason=finish_reason)


def parse_sse_data(output: str) -> Optional[str]:
    r"""Parse the SSE data.

    Just keep the data part.

    Examples:
        .. code-block:: python

            from dbgpt.core.awel.util.chat_util import parse_sse_data

            assert parse_sse_data("data: [DONE]") == "[DONE]"
            assert parse_sse_data("data:[DONE]") == "[DONE]"
            assert parse_sse_data("data: Hello") == "Hello"
            assert parse_sse_data("data: Hello\n") == "Hello"
            assert parse_sse_data("data: Hello\r\n") == "Hello"
            assert parse_sse_data("data: Hi, what's up?") == "Hi, what's up?"

    Args:
        output (str): The output.

    Returns:
        Optional[str]: The parsed data.
    """
    if output.startswith("data:"):
        output = output.strip()
        if output.startswith("data: "):
            output = output[6:]
        else:
            output = output[5:]

        return output
    else:
        return None
