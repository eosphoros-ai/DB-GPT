import copy
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.util import BaseParameters
from dbgpt.util.annotations import PublicAPI
from dbgpt.util.model_utils import GPUInfo


@dataclass
@PublicAPI(stability="beta")
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
@PublicAPI(stability="beta")
class ModelRequestContext:
    stream: Optional[bool] = False
    """Whether to return a stream of responses."""

    user_name: Optional[str] = None
    """The user name of the model request."""

    sys_code: Optional[str] = None
    """The system code of the model request."""

    conv_uid: Optional[str] = None
    """The conversation id of the model inference."""

    span_id: Optional[str] = None
    """The span id of the model inference."""

    extra: Optional[Dict[str, Any]] = field(default_factory=dict)
    """The extra information of the model inference."""


@dataclass
@PublicAPI(stability="beta")
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
@PublicAPI(stability="beta")
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

    context: Optional[ModelRequestContext] = field(
        default_factory=lambda: ModelRequestContext()
    )
    """The context of the model inference."""

    @property
    def stream(self) -> bool:
        """Whether to return a stream of responses."""
        return self.context and self.context.stream

    def copy(self):
        new_request = copy.deepcopy(self)
        # Transform messages to List[ModelMessage]
        new_request.messages = list(
            map(
                lambda m: m if isinstance(m, ModelMessage) else ModelMessage(**m),
                new_request.messages,
            )
        )
        return new_request

    def to_dict(self) -> Dict[str, Any]:
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

    def get_single_user_message(self) -> Optional[ModelMessage]:
        """Get the single user message.

        Returns:
            Optional[ModelMessage]: The single user message.
        """
        messages = self._get_messages()
        if len(messages) != 1 and messages[0].role != ModelMessageRoleType.HUMAN:
            raise ValueError("The messages is not a single user message")
        return messages[0]

    @staticmethod
    def _build(model: str, prompt: str, **kwargs):
        return ModelRequest(
            model=model,
            messages=[ModelMessage(role=ModelMessageRoleType.HUMAN, content=prompt)],
            **kwargs,
        )

    def to_openai_messages(self) -> List[Dict[str, Any]]:
        """Convert the messages to the format of OpenAI API.

        This function will move last user message to the end of the list.

        Returns:
            List[Dict[str, Any]]: The messages in the format of OpenAI API.

        Examples:

            .. code-block:: python

                from dbgpt.core.interface.message import (
                    ModelMessage,
                    ModelMessageRoleType,
                )

                messages = [
                    ModelMessage(role=ModelMessageRoleType.HUMAN, content="Hi"),
                    ModelMessage(
                        role=ModelMessageRoleType.AI, content="Hi, I'm a robot."
                    ),
                    ModelMessage(
                        role=ModelMessageRoleType.HUMAN, content="Who are your"
                    ),
                ]
                openai_messages = ModelRequest.to_openai_messages(messages)
                assert openai_messages == [
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hi, I'm a robot."},
                    {"role": "user", "content": "Who are your"},
                ]
        """
        messages = [
            m if isinstance(m, ModelMessage) else ModelMessage(**m)
            for m in self.messages
        ]
        return ModelMessage.to_openai_messages(messages)


@dataclass
@PublicAPI(stability="beta")
class ModelMetadata(BaseParameters):
    """A class to represent a LLM model."""

    model: str = field(
        metadata={"help": "Model name"},
    )
    context_length: Optional[int] = field(
        default=4096,
        metadata={"help": "Context length of model"},
    )
    chat_model: Optional[bool] = field(
        default=True,
        metadata={"help": "Whether the model is a chat model"},
    )
    is_function_calling_model: Optional[bool] = field(
        default=False,
        metadata={"help": "Whether the model is a function calling model"},
    )
    metadata: Optional[Dict[str, Any]] = field(
        default_factory=dict,
        metadata={"help": "Model metadata"},
    )


@PublicAPI(stability="beta")
class LLMClient(ABC):
    """An abstract class for LLM client."""

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelOutput:
        """Generate a response for a given model request.

        Args:
            request(ModelRequest): The model request.

        Returns:
            ModelOutput: The model output.

        """

    @abstractmethod
    async def generate_stream(
        self, request: ModelRequest
    ) -> AsyncIterator[ModelOutput]:
        """Generate a stream of responses for a given model request.

        Args:
            request(ModelRequest): The model request.

        Returns:
            AsyncIterator[ModelOutput]: The model output stream.
        """

    @abstractmethod
    async def models(self) -> List[ModelMetadata]:
        """Get all the models.

        Returns:
            List[ModelMetadata]: A list of model metadata.
        """

    @abstractmethod
    async def count_token(self, model: str, prompt: str) -> int:
        """Count the number of tokens in a given prompt.

        Args:
            model(str): The model name.
            prompt(str): The prompt.

        Returns:
            int: The number of tokens.
        """
