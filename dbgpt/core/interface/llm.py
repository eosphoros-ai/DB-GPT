from abc import ABC
from typing import Optional, Dict, List, Any, Union, AsyncIterator

import time
from dataclasses import dataclass, asdict
import copy

from dbgpt.util.annotations import PublicAPI
from dbgpt.util.model_utils import GPUInfo
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.core.awel import MapOperator, StreamifyAbsOperator


@dataclass
class ModelInferenceMetrics:
    """A class to represent metrics for assessing the inference performance of a LLM."""

    collect_index: Optional[int] = 0

    start_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the model inference starts."""

    end_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the model inference ends."""

    current_time_ms: Optional[int] = None
    """The current timestamp (in milliseconds) when the model inference return partially output(stream)."""

    first_token_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the first token is generated."""

    first_completion_time_ms: Optional[int] = None
    """The timestamp (in milliseconds) when the first completion is generated."""

    first_completion_tokens: Optional[int] = None
    """The number of tokens when the first completion is generated."""

    prompt_tokens: Optional[int] = None
    """The number of tokens in the input prompt."""

    completion_tokens: Optional[int] = None
    """The number of tokens in the generated completion."""

    total_tokens: Optional[int] = None
    """The total number of tokens (prompt plus completion)."""

    speed_per_second: Optional[float] = None
    """The average number of tokens generated per second."""

    current_gpu_infos: Optional[List[GPUInfo]] = None
    """Current gpu information, all devices"""

    avg_gpu_infos: Optional[List[GPUInfo]] = None
    """Average memory usage across all collection points"""

    @staticmethod
    def create_metrics(
        last_metrics: Optional["ModelInferenceMetrics"] = None,
    ) -> "ModelInferenceMetrics":
        start_time_ms = last_metrics.start_time_ms if last_metrics else None
        first_token_time_ms = last_metrics.first_token_time_ms if last_metrics else None
        first_completion_time_ms = (
            last_metrics.first_completion_time_ms if last_metrics else None
        )
        first_completion_tokens = (
            last_metrics.first_completion_tokens if last_metrics else None
        )
        prompt_tokens = last_metrics.prompt_tokens if last_metrics else None
        completion_tokens = last_metrics.completion_tokens if last_metrics else None
        total_tokens = last_metrics.total_tokens if last_metrics else None
        speed_per_second = last_metrics.speed_per_second if last_metrics else None
        current_gpu_infos = last_metrics.current_gpu_infos if last_metrics else None
        avg_gpu_infos = last_metrics.avg_gpu_infos if last_metrics else None

        if not start_time_ms:
            start_time_ms = time.time_ns() // 1_000_000
        current_time_ms = time.time_ns() // 1_000_000
        end_time_ms = current_time_ms

        return ModelInferenceMetrics(
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            current_time_ms=current_time_ms,
            first_token_time_ms=first_token_time_ms,
            first_completion_time_ms=first_completion_time_ms,
            first_completion_tokens=first_completion_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            speed_per_second=speed_per_second,
            current_gpu_infos=current_gpu_infos,
            avg_gpu_infos=avg_gpu_infos,
        )

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ModelOutput:
    """A class to represent the output of a LLM.""" ""

    text: str
    """The generated text."""
    error_code: int
    """The error code of the model inference. If the model inference is successful, the error code is 0."""
    model_context: Dict = None
    finish_reason: str = None
    usage: Dict[str, Any] = None
    metrics: Optional[ModelInferenceMetrics] = None
    """Some metrics for model inference"""

    def to_dict(self) -> Dict:
        return asdict(self)


_ModelMessageType = Union[ModelMessage, Dict[str, Any]]


@dataclass
class ModelRequest:
    model: str
    """The name of the model."""

    messages: List[_ModelMessageType]
    """The input messages."""

    temperature: Optional[float] = None
    """The temperature of the model inference."""

    max_new_tokens: Optional[int] = None
    """The maximum number of tokens to generate."""

    stop: Optional[str] = None
    """The stop condition of the model inference."""
    stop_token_ids: Optional[List[int]] = None
    """The stop token ids of the model inference."""
    context_len: Optional[int] = None
    """The context length of the model inference."""
    echo: Optional[bool] = True
    """Whether to echo the input messages."""
    span_id: Optional[str] = None
    """The span id of the model inference."""

    def to_dict(self) -> Dict:
        new_reqeust = copy.deepcopy(self)
        new_reqeust.messages = list(
            map(lambda m: m if isinstance(m, dict) else m.dict(), new_reqeust.messages)
        )
        # Skip None fields
        return {k: v for k, v in asdict(new_reqeust).items() if v}

    def _get_messages(self) -> List[ModelMessage]:
        return list(
            map(
                lambda m: m if isinstance(m, ModelMessage) else ModelMessage(**m),
                self.messages,
            )
        )

    @staticmethod
    def _build(model: str, prompt: str, **kwargs):
        return ModelRequest(
            model=model,
            messages=[ModelMessage(role=ModelMessageRoleType.HUMAN, content=prompt)],
            **kwargs,
        )


class RequestBuildOperator(MapOperator[str, ModelRequest], ABC):
    def __init__(self, model: str, **kwargs):
        self._model = model
        super().__init__(**kwargs)

    async def map(self, input_value: str) -> ModelRequest:
        return ModelRequest._build(self._model, input_value)


class BaseLLMOperator(
    MapOperator[ModelRequest, ModelOutput],
    StreamifyAbsOperator[ModelRequest, ModelOutput],
    ABC,
):
    """The abstract operator for a LLM."""


@PublicAPI(stability="beta")
class OpenAILLM(BaseLLMOperator):
    """The operator for OpenAI LLM.

    Examples:

        .. code-block:: python
            llm = OpenAILLM()
            model_request = ModelRequest(model="gpt-3.5-turbo", messages=[ModelMessage(role=ModelMessageRoleType.HUMAN, content="Hello")])
            model_output = await llm.map(model_request)
    """

    def __int__(self):
        try:
            import openai
        except ImportError as e:
            raise ImportError("Please install openai package to use OpenAILLM") from e
        import importlib.metadata as metadata

        if not metadata.version("openai") >= "1.0.0":
            raise ImportError("Please upgrade openai package to version 1.0.0 or above")

    async def _send_request(
        self, model_request: ModelRequest, stream: Optional[bool] = False
    ):
        import os
        from openai import AsyncOpenAI

        client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("OPENAI_API_BASE"),
        )
        messages = ModelMessage.to_openai_messages(model_request._get_messages())
        payloads = {
            "model": model_request.model,
            "stream": stream,
        }
        if model_request.temperature is not None:
            payloads["temperature"] = model_request.temperature
        if model_request.max_new_tokens:
            payloads["max_tokens"] = model_request.max_new_tokens

        return await client.chat.completions.create(messages=messages, **payloads)

    async def map(self, model_request: ModelRequest) -> ModelOutput:
        try:
            chat_completion = await self._send_request(model_request, stream=False)
            text = chat_completion.choices[0].message.content
            usage = chat_completion.usage.dict()
            return ModelOutput(text=text, error_code=0, usage=usage)
        except Exception as e:
            return ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )

    async def streamify(
        self, model_request: ModelRequest
    ) -> AsyncIterator[ModelOutput]:
        try:
            chat_completion = await self._send_request(model_request, stream=True)
            text = ""
            for r in chat_completion:
                if len(r.choices) == 0:
                    continue
                if r.choices[0].delta.content is not None:
                    content = r.choices[0].delta.content
                    text += content
                    yield ModelOutput(text=text, error_code=0)
        except Exception as e:
            yield ModelOutput(
                text=f"**LLMServer Generate Error, Please CheckErrorInfo.**: {e}",
                error_code=1,
            )
