import collections
import copy
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from cachetools import TTLCache

from dbgpt._private.pydantic import BaseModel
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.util import BaseParameters
from dbgpt.util.annotations import PublicAPI
from dbgpt.util.model_utils import GPUInfo

logger = logging.getLogger(__name__)


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

    chat_mode: Optional[str] = None
    """The chat mode of the model inference."""

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

    def get_messages(self) -> List[ModelMessage]:
        """Get the messages.

        If the messages is not a list of ModelMessage, it will be converted to a list of ModelMessage.
        Returns:
            List[ModelMessage]: The messages.
        """
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
        messages = self.get_messages()
        if len(messages) != 1 and messages[0].role != ModelMessageRoleType.HUMAN:
            raise ValueError("The messages is not a single user message")
        return messages[0]

    @staticmethod
    def build_request(
        model: str,
        messages: List[ModelMessage],
        context: Union[ModelRequestContext, Dict[str, Any], BaseModel],
        stream: Optional[bool] = False,
        **kwargs,
    ):
        context_dict = None
        if isinstance(context, dict):
            context_dict = context
        elif isinstance(context, BaseModel):
            context_dict = context.dict()
        if context_dict and "stream" not in context_dict:
            context_dict["stream"] = stream
            context = ModelRequestContext(**context_dict)
        return ModelRequest(
            model=model,
            messages=messages,
            context=context,
            **kwargs,
        )

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
class ModelExtraMedata(BaseParameters):
    """A class to represent the extra metadata of a LLM."""

    prompt_roles: Optional[List[str]] = field(
        default_factory=lambda: [
            ModelMessageRoleType.SYSTEM,
            ModelMessageRoleType.HUMAN,
            ModelMessageRoleType.AI,
        ],
        metadata={"help": "The roles of the prompt"},
    )

    prompt_sep: Optional[str] = field(
        default="\n",
        metadata={"help": "The separator of the prompt between multiple rounds"},
    )

    # You can see the chat template in your model repo tokenizer config,
    # typically in the tokenizer_config.json
    prompt_chat_template: Optional[str] = field(
        default=None,
        metadata={
            "help": "The chat template, see: https://huggingface.co/docs/transformers/main/en/chat_templating"
        },
    )

    @property
    def support_system_message(self) -> bool:
        """Whether the model supports system message.

        Returns:
            bool: Whether the model supports system message.
        """
        return ModelMessageRoleType.SYSTEM in self.prompt_roles


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
    ext_metadata: Optional[ModelExtraMedata] = field(
        default_factory=ModelExtraMedata,
        metadata={"help": "Model extra metadata"},
    )

    @classmethod
    def from_dict(
        cls, data: dict, ignore_extra_fields: bool = False
    ) -> "ModelMetadata":
        if "ext_metadata" in data:
            data["ext_metadata"] = ModelExtraMedata(**data["ext_metadata"])
        return cls(**data)


class MessageConverter(ABC):
    """An abstract class for message converter.

    Different LLMs may have different message formats, this class is used to convert the messages
    to the format of the LLM.

    Examples:

        >>> from typing import List
        >>> from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
        >>> from dbgpt.core.interface.llm import MessageConverter, ModelMetadata
        >>> class RemoveSystemMessageConverter(MessageConverter):
        ...     def convert(
        ...         self,
        ...         messages: List[ModelMessage],
        ...         model_metadata: Optional[ModelMetadata] = None,
        ...     ) -> List[ModelMessage]:
        ...         # Convert the messages, merge system messages to the last user message.
        ...         system_message = None
        ...         other_messages = []
        ...         sep = "\\n"
        ...         for message in messages:
        ...             if message.role == ModelMessageRoleType.SYSTEM:
        ...                 system_message = message
        ...             else:
        ...                 other_messages.append(message)
        ...         if system_message and other_messages:
        ...             other_messages[-1].content = (
        ...                 system_message.content + sep + other_messages[-1].content
        ...             )
        ...         return other_messages
        ...
        >>> messages = [
        ...     ModelMessage(
        ...         role=ModelMessageRoleType.SYSTEM,
        ...         content="You are a helpful assistant",
        ...     ),
        ...     ModelMessage(role=ModelMessageRoleType.HUMAN, content="Who are you"),
        ... ]
        >>> converter = RemoveSystemMessageConverter()
        >>> converted_messages = converter.convert(messages, None)
        >>> assert converted_messages == [
        ...     ModelMessage(
        ...         role=ModelMessageRoleType.HUMAN,
        ...         content="You are a helpful assistant\\nWho are you",
        ...     ),
        ... ]
    """

    @abstractmethod
    def convert(
        self,
        messages: List[ModelMessage],
        model_metadata: Optional[ModelMetadata] = None,
    ) -> List[ModelMessage]:
        """Convert the messages.

        Args:
            messages(List[ModelMessage]): The messages.
            model_metadata(ModelMetadata): The model metadata.

        Returns:
            List[ModelMessage]: The converted messages.
        """


class DefaultMessageConverter(MessageConverter):
    """The default message converter."""

    def __init__(self, prompt_sep: Optional[str] = None):
        self._prompt_sep = prompt_sep

    def convert(
        self,
        messages: List[ModelMessage],
        model_metadata: Optional[ModelMetadata] = None,
    ) -> List[ModelMessage]:
        """Convert the messages.

        There are three steps to convert the messages:

        1. Just keep system, human and AI messages

        2. Move the last user's message to the end of the list

        3. Convert the messages to no system message if the model does not support system message

        Args:
            messages(List[ModelMessage]): The messages.
            model_metadata(ModelMetadata): The model metadata.

        Returns:
            List[ModelMessage]: The converted messages.
        """
        # 1. Just keep system, human and AI messages
        messages = list(filter(lambda m: m.pass_to_model, messages))
        # 2. Move the last user's message to the end of the list
        messages = self.move_last_user_message_to_end(messages)

        if not model_metadata or not model_metadata.ext_metadata:
            logger.warning("No model metadata, skip message system message conversion")
            return messages
        if model_metadata.ext_metadata.support_system_message:
            # 3. Convert the messages to no system message
            return self.convert_to_no_system_message(messages, model_metadata)
        return messages

    def convert_to_no_system_message(
        self,
        messages: List[ModelMessage],
        model_metadata: Optional[ModelMetadata] = None,
    ) -> List[ModelMessage]:
        """Convert the messages to no system message.

        Examples:
            >>> # Convert the messages to no system message, just merge system messages to the last user message
            >>> from typing import List
            >>> from dbgpt.core.interface.message import (
            ...     ModelMessage,
            ...     ModelMessageRoleType,
            ... )
            >>> from dbgpt.core.interface.llm import (
            ...     DefaultMessageConverter,
            ...     ModelMetadata,
            ... )
            >>> messages = [
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.SYSTEM,
            ...         content="You are a helpful assistant",
            ...     ),
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.HUMAN, content="Who are you"
            ...     ),
            ... ]
            >>> converter = DefaultMessageConverter()
            >>> model_metadata = ModelMetadata(model="test")
            >>> converted_messages = converter.convert_to_no_system_message(
            ...     messages, model_metadata
            ... )
            >>> assert converted_messages == [
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.HUMAN,
            ...         content="You are a helpful assistant\\nWho are you",
            ...     ),
            ... ]
        """
        if not model_metadata or not model_metadata.ext_metadata:
            logger.warning("No model metadata, skip message conversion")
            return messages
        ext_metadata = model_metadata.ext_metadata
        system_messages = []
        result_messages = []
        for message in messages:
            if message.role == ModelMessageRoleType.SYSTEM:
                # Not support system message, append system message to the last user message
                system_messages.append(message)
            elif message.role in [
                ModelMessageRoleType.HUMAN,
                ModelMessageRoleType.AI,
            ]:
                result_messages.append(message)
        prompt_sep = self._prompt_sep or ext_metadata.prompt_sep or "\n"
        system_message_str = None
        if len(system_messages) > 1:
            logger.warning("Your system messages have more than one message")
            system_message_str = prompt_sep.join([m.content for m in system_messages])
        elif len(system_messages) == 1:
            system_message_str = system_messages[0].content

        if system_message_str and result_messages:
            #  Not support system messages, merge system messages to the last user message
            result_messages[-1].content = (
                system_message_str + prompt_sep + result_messages[-1].content
            )
        return result_messages

    def move_last_user_message_to_end(
        self, messages: List[ModelMessage]
    ) -> List[ModelMessage]:
        """Move the last user message to the end of the list.

        Examples:

            >>> from typing import List
            >>> from dbgpt.core.interface.message import (
            ...     ModelMessage,
            ...     ModelMessageRoleType,
            ... )
            >>> from dbgpt.core.interface.llm import DefaultMessageConverter
            >>> messages = [
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.SYSTEM,
            ...         content="You are a helpful assistant",
            ...     ),
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.HUMAN, content="Who are you"
            ...     ),
            ...     ModelMessage(role=ModelMessageRoleType.AI, content="I'm a robot"),
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.HUMAN, content="What's your name"
            ...     ),
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.SYSTEM,
            ...         content="You are a helpful assistant",
            ...     ),
            ... ]
            >>> converter = DefaultMessageConverter()
            >>> converted_messages = converter.move_last_user_message_to_end(messages)
            >>> assert converted_messages == [
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.SYSTEM,
            ...         content="You are a helpful assistant",
            ...     ),
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.HUMAN, content="Who are you"
            ...     ),
            ...     ModelMessage(role=ModelMessageRoleType.AI, content="I'm a robot"),
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.SYSTEM,
            ...         content="You are a helpful assistant",
            ...     ),
            ...     ModelMessage(
            ...         role=ModelMessageRoleType.HUMAN, content="What's your name"
            ...     ),
            ... ]

        Args:
            messages(List[ModelMessage]): The messages.

        Returns:
            List[ModelMessage]: The converted messages.
        """
        last_user_input_index = None
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == ModelMessageRoleType.HUMAN:
                last_user_input_index = i
                break
        if last_user_input_index is not None:
            last_user_input = messages.pop(last_user_input_index)
            messages.append(last_user_input)
        return messages


@PublicAPI(stability="beta")
class LLMClient(ABC):
    """An abstract class for LLM client."""

    # Cache the model metadata for 60 seconds
    _MODEL_CACHE_ = TTLCache(maxsize=100, ttl=60)

    @property
    def cache(self) -> collections.abc.MutableMapping:
        """The cache object to cache the model metadata.

        You can override this property to use your own cache object.
        Returns:
            collections.abc.MutableMapping: The cache object.
        """
        return self._MODEL_CACHE_

    @abstractmethod
    async def generate(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelOutput:
        """Generate a response for a given model request.

        Sometimes, different LLMs may have different message formats,
        you can use the message converter to convert the messages to the format of the LLM.

        Args:
            request(ModelRequest): The model request.
            message_converter(MessageConverter): The message converter.

        Returns:
            ModelOutput: The model output.

        """

    @abstractmethod
    async def generate_stream(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> AsyncIterator[ModelOutput]:
        """Generate a stream of responses for a given model request.

        Sometimes, different LLMs may have different message formats,
        you can use the message converter to convert the messages to the format of the LLM.

        Args:
            request(ModelRequest): The model request.
            message_converter(MessageConverter): The message converter.

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

    async def covert_message(
        self,
        request: ModelRequest,
        message_converter: Optional[MessageConverter] = None,
    ) -> ModelRequest:
        """Covert the message.
        If no message converter is provided, the original request will be returned.

        Args:
            request(ModelRequest): The model request.
            message_converter(MessageConverter): The message converter.

        Returns:
            ModelRequest: The converted model request.
        """
        if not message_converter:
            return request
        new_request = request.copy()
        model_metadata = await self.get_model_metadata(request.model)
        new_messages = message_converter.convert(request.messages, model_metadata)
        new_request.messages = new_messages
        return new_request

    async def cached_models(self) -> List[ModelMetadata]:
        """Get all the models from the cache or the llm server.

        If the model metadata is not in the cache, it will be fetched from the llm server.

        Returns:
            List[ModelMetadata]: A list of model metadata.
        """
        key = "____$llm_client_models$____"
        if key not in self.cache:
            models = await self.models()
            self.cache[key] = models
            for model in models:
                model_metadata_key = (
                    f"____$llm_client_models_metadata_{model.model}$____"
                )
                self.cache[model_metadata_key] = model
        return self.cache[key]

    async def get_model_metadata(self, model: str) -> ModelMetadata:
        """Get the model metadata.

        Args:
            model(str): The model name.

        Returns:
            ModelMetadata: The model metadata.

        Raises:
            ValueError: If the model is not found.
        """
        model_metadata_key = f"____$llm_client_models_metadata_{model}$____"
        if model_metadata_key not in self.cache:
            await self.cached_models()
        model_metadata = self.cache.get(model_metadata_key)
        if not model_metadata:
            raise ValueError(f"Model {model} not found")
        return model_metadata
