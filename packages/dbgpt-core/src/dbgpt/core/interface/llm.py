"""The interface for LLM."""

import collections
import copy
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import (
    Any,
    AsyncIterator,
    Coroutine,
    Dict,
    List,
    Literal,
    Optional,
    Tuple,
    Union,
)

from cachetools import TTLCache

from dbgpt._private.pydantic import BaseModel, model_to_dict
from dbgpt.core.interface.message import ModelMessage, ModelMessageRoleType
from dbgpt.util import BaseParameters
from dbgpt.util.annotations import PublicAPI
from dbgpt.util.i18n_utils import _
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
    """The current timestamp (in milliseconds) when the model inference return
    partially output(stream)."""

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
        """Create metrics for model inference.

        Args:
            last_metrics(ModelInferenceMetrics): The last metrics.

        Returns:
            ModelInferenceMetrics: The metrics for model inference.
        """
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
        """Convert the model inference metrics to dict."""
        return asdict(self)


MEDIA_DATA_TYPE = Union[str, bytes]


@dataclass
class MediaObject:
    """Media object for the model output or model request."""

    data: MEDIA_DATA_TYPE = field(metadata={"help": _("The media data")})
    format: str = field(default="text", metadata={"help": _("The format of the media")})


class MediaContentType(str, Enum):
    """The media content type."""

    TEXT = "text"
    THINKING = "thinking"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"


@dataclass
class MediaContent:
    """Media content for the model output or model request.

    Examples:
        .. code-block:: python

        simple_text = MediaContent(
            type="text",
            object=MediaObject(
                data="Hello, world!",
                format="text",
            )
        )
        thinking_text = MediaContent(
            type="thinking",
            object=MediaObject(
                data="Thinking...",
                format="text",
            )
        )

        url_image1 = MediaContent(
            type="image",
            object=MediaObject(
                data="https://example.com/image.jpg",
                format="url",
            )
        )
        # Url with image type: 'image/jpeg'
        url_image2 = MediaContent(
            type="image",
            object=MediaObject(
                data="https://example.com/image.jpg",
                format="url@image/jpeg",
            )
        )

        # With image type: 'image/jpeg'
        base64_image1 = MediaContent(
            type="image",
            object=MediaObject(
                data="base64_string",
                format="base64@image/jpeg",
            )
        )
        # No image type
        base64_image2 = MediaContent(
            type="image",
            object=MediaObject(
                data="base64_string",
                format="base64",
            )
        )

        # Video
        url_video1 = MediaContent(
            type="video",
            object=MediaObject(
                data="https://example.com/video.mp4",
                format="url",
            )
        )
        url_video2 = MediaContent(
            type="video",
            object=MediaObject(
                data="https://example.com/video.mp4",
                format="url@video/mp4",
            )
        )
        binary_video = MediaContent(
            type="video",
            object=MediaObject(
                data=b"binary_data",
                format="binary@video/mp4",
            )
        )
        binary_audio = MediaContent(
            type="audio",
            object=MediaObject(
                data=b"binary_data",
                format="binary@audio/mpeg",
            )
        )
    """

    object: MediaObject = field(metadata={"help": _("The media object")})
    type: Literal["text", "thinking", "image", "audio", "video"] = field(
        default="text", metadata={"help": _("The type of the model media content")}
    )

    @classmethod
    def build_text(cls, text: str) -> "MediaContent":
        """Create a MediaContent object from text."""
        return cls(type="text", object=MediaObject(data=text, format="text"))

    @classmethod
    def build_thinking(cls, text: str) -> "MediaContent":
        """Create a MediaContent object from thinking."""
        return cls(type="thinking", object=MediaObject(data=text, format="text"))

    def get_text(self) -> str:
        """Get the text."""
        if self.type == MediaContentType.TEXT:
            return self.object.data
        raise ValueError("The content type is not text")

    def get_thinking(self) -> str:
        """Get the thinking."""
        if self.type == MediaContentType.THINKING:
            return self.object.data
        raise ValueError("The content type is not thinking")


@dataclass
@PublicAPI(stability="beta")
class ModelRequestContext:
    """A class to represent the context of a LLM model request."""

    stream: bool = False
    """Whether to return a stream of responses."""

    cache_enable: bool = False
    """Whether to enable the cache for the model inference"""

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

    chat_param: Optional[str] = None
    """The chat param of chat mode"""

    extra: Optional[Dict[str, Any]] = field(default_factory=dict)
    """The extra information of the model inference."""

    request_id: Optional[str] = None
    """The request id of the model inference."""

    is_reasoning_model: Optional[bool] = False
    """Whether the model is a reasoning model."""


@dataclass
@PublicAPI(stability="beta")
class ModelOutput:
    """A class to represent the output of a LLM."""

    content: Union[MediaContent, List[MediaContent]]
    """The generated text."""
    error_code: int
    """The error code of the model inference. If the model inference is successful,
    the error code is 0."""
    incremental: bool = False
    model_context: Optional[Dict] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    metrics: Optional[ModelInferenceMetrics] = None
    """Some metrics for model inference"""

    def __init__(
        self,
        error_code: int,
        text: Optional[str] = None,
        content: Optional[MediaContent] = None,
        **kwargs,
    ):
        if text is not None and content is not None:
            raise ValueError("Cannot pass both text and content")
        elif text is not None:
            self.content = MediaContent.build_text(text)
        elif content is not None:
            self.content = content
        else:
            raise ValueError("Must pass either text or content")
        self.error_code = error_code
        for k, v in kwargs.items():
            if k in [
                "incremental",
                "model_context",
                "finish_reason",
                "usage",
                "metrics",
            ]:
                setattr(self, k, v)

    def to_dict(self) -> Dict:
        """Convert the model output to dict."""
        text = self.gen_text_with_thinking()
        return {
            "error_code": self.error_code,
            "text": text,
            "incremental": self.incremental,
            "model_context": self.model_context,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "metrics": self.metrics,
        }

    @property
    def success(self) -> bool:
        """Check if the model inference is successful."""
        return self.error_code == 0

    @property
    def has_text(self) -> bool:
        """Check if the model output has text content."""
        if isinstance(self.content, MediaContent):
            return self.content.type == MediaContentType.TEXT
        elif isinstance(self.content, list):
            return any(c.type == MediaContentType.TEXT for c in self.content)
        return False

    @property
    def text(self) -> str:
        """The generated text."""
        if isinstance(self.content, MediaContent):
            return self.content.get_text()
        elif isinstance(self.content, list) and all(
            isinstance(c, MediaContent) for c in self.content
        ):
            text_content = [c for c in self.content if c.type == MediaContentType.TEXT]
            if not text_content:
                raise ValueError("There is no text content")
            # Return the last text content
            return text_content[-1].get_text()
        raise ValueError("The content is not text")

    @property
    def has_thinking(self) -> bool:
        """Check if the model output has thinking content."""
        if isinstance(self.content, MediaContent):
            return self.content.type == MediaContentType.THINKING
        elif isinstance(self.content, list) and self.content:
            return any(c.type == MediaContentType.THINKING for c in self.content)
        else:
            return False

    @property
    def thinking_text(self) -> Optional[str]:
        """The reasoning content."""
        if not self.content:
            return None
        if isinstance(self.content, MediaContent):
            if self.content.type == MediaContentType.THINKING:
                return self.content.get_thinking()
            return None
        elif isinstance(self.content, list) and all(
            isinstance(c, MediaContent) for c in self.content
        ):
            # In most cases, just one thinking content
            thinking_content = [
                c for c in self.content if c.type == MediaContentType.THINKING
            ]
            if not thinking_content:
                return None
            # Return the last thinking content
            return thinking_content[-1].get_thinking()
        return None

    def gen_text_with_thinking(self, new_text: Optional[str] = None) -> str:
        from dbgpt.vis.tags.vis_thinking import VisThinking

        msg = ""
        if self.has_thinking:
            msg = self.thinking_text or ""
            msg = VisThinking().sync_display(content=msg)
            msg += "\n"
        if new_text:
            msg += new_text
        elif self.has_text:
            msg += self.text or ""
        return msg

    @text.setter
    def text(self, value: str):
        """Set the generated text."""
        if not isinstance(value, str):
            raise ValueError("text must be a string")
        # Build a new MediaContent object and assign it to content
        self.content = MediaContent(
            type="text",
            object=MediaObject(data=value, format="text"),
        )

    @classmethod
    def build_thinking(cls, thinking: str, error_code: int = 0) -> "ModelOutput":
        """Create a ModelOutput object from thinking."""
        return cls(
            error_code=error_code,
            content=MediaContent.build_thinking(thinking),
        )

    @classmethod
    def build(
        cls,
        text: Optional[str] = None,
        thinking: Optional[str] = None,
        error_code: int = 0,
        usage: Optional[Dict[str, Any]] = None,
        finish_reason: Optional[str] = None,
        is_reasoning_model: bool = False,
        metrics: Optional[ModelInferenceMetrics] = None,
    ) -> "ModelOutput":
        if thinking and text:
            # Has thinking and text
            content = [
                # First thinking
                MediaContent.build_thinking(thinking),
                MediaContent.build_text(text),
            ]
        elif text:
            # Only text
            content = MediaContent.build_text(text)
        elif is_reasoning_model or thinking:
            # Build a empty thinking content
            # Handle empty data
            content = MediaContent.build_thinking(thinking)
        else:
            content = MediaContent.build_text("")

        return cls(
            error_code=error_code,
            content=content,
            usage=usage,
            finish_reason=finish_reason,
            metrics=metrics,
        )

    @property
    def error_message(self) -> str:
        """Get the error message.
        Just return the error message when error_code is not 0.
        """
        return self.text if self.has_text else "Unknown error"


_ModelMessageType = Union[List[ModelMessage], List[Dict[str, Any]]]


@dataclass
@PublicAPI(stability="beta")
class ModelRequest:
    """The model request."""

    model: str
    """The name of the model."""

    messages: _ModelMessageType
    """The input messages."""

    temperature: Optional[float] = None
    """The temperature of the model inference."""

    top_p: Optional[float] = None
    """The top p of the model inference."""

    max_new_tokens: Optional[int] = None
    """The maximum number of tokens to generate."""

    stop: Optional[Union[str, List[str]]] = None
    """The stop condition of the model inference."""
    stop_token_ids: Optional[List[int]] = None
    """The stop token ids of the model inference."""
    context_len: Optional[int] = None
    """The context length of the model inference."""
    echo: Optional[bool] = False
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
        return bool(self.context and self.context.stream)

    def copy(self) -> "ModelRequest":
        """Copy the model request.

        Returns:
            ModelRequest: The copied model request.
        """
        new_request = copy.deepcopy(self)
        # Transform messages to List[ModelMessage]
        new_request.messages = new_request.get_messages()
        return new_request

    def to_dict(self) -> Dict[str, Any]:
        """Convert the model request to dict.

        Returns:
            Dict[str, Any]: The model request in dict.
        """
        new_reqeust = copy.deepcopy(self)
        new_messages = []
        for message in new_reqeust.messages:
            if isinstance(message, dict):
                new_messages.append(message)
            else:
                new_messages.append(message.dict())
        new_reqeust.messages = new_messages
        # Skip None fields
        return {k: v for k, v in asdict(new_reqeust).items() if v is not None}

    def to_trace_metadata(self) -> Dict[str, Any]:
        """Convert the model request to trace metadata.

        Returns:
            Dict[str, Any]: The trace metadata.
        """
        metadata = self.to_dict()
        metadata["prompt"] = self.messages_to_string()
        return metadata

    def get_messages(self) -> List[ModelMessage]:
        """Get the messages.

        If the messages is not a list of ModelMessage, it will be converted to a list
        of ModelMessage.

        Returns:
            List[ModelMessage]: The messages.
        """
        messages = []
        for message in self.messages:
            if isinstance(message, dict):
                messages.append(ModelMessage(**message))
            else:
                messages.append(message)
        return messages

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
        context: Optional[Union[ModelRequestContext, Dict[str, Any], BaseModel]] = None,
        stream: bool = False,
        echo: bool = False,
        **kwargs,
    ):
        """Build a model request.

        Args:
            model(str): The model name.
            messages(List[ModelMessage]): The messages.
            context(Optional[Union[ModelRequestContext, Dict[str, Any], BaseModel]]):
                The context.
            stream(bool): Whether to return a stream of responses. Defaults to False.
            echo(bool): Whether to echo the input messages. Defaults to False.
            **kwargs: Other arguments.
        """
        if not context:
            context = ModelRequestContext(stream=stream)
        elif not isinstance(context, ModelRequestContext):
            context_dict = None
            if isinstance(context, dict):
                context_dict = context
            elif isinstance(context, BaseModel):
                context_dict = model_to_dict(context)
            if context_dict and "stream" not in context_dict:
                context_dict["stream"] = stream
            if context_dict:
                context = ModelRequestContext(**context_dict)
            else:
                context = ModelRequestContext(stream=stream)
        return ModelRequest(
            model=model,
            messages=messages,
            context=context,
            echo=echo,
            **kwargs,
        )

    @staticmethod
    def _build(model: str, prompt: str, **kwargs):
        return ModelRequest(
            model=model,
            messages=[ModelMessage(role=ModelMessageRoleType.HUMAN, content=prompt)],
            **kwargs,
        )

    def to_common_messages(
        self, support_system_role: bool = True
    ) -> List[Dict[str, Any]]:
        """Convert the messages to the common format(like OpenAI API).

        This function will move last user message to the end of the list.

        Args:
            support_system_role (bool): Whether to support system role

        Returns:
            List[Dict[str, Any]]: The messages in the format of OpenAI API.

        Raises:
            ValueError: If the message role is not supported

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
        return ModelMessage.to_common_messages(
            messages, support_system_role=support_system_role
        )

    def messages_to_string(self) -> str:
        """Convert the messages to string.

        Returns:
            str: The messages in string format.
        """
        return ModelMessage.messages_to_string(self.get_messages())

    def split_messages(self) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Split the messages.

        Returns:
            Tuple[List[Dict[str, Any]], List[str]]: The common messages and system
            messages.
        """
        messages = self.get_messages()
        common_messages = []
        system_messages = []
        for message in messages:
            if message.role == ModelMessageRoleType.HUMAN:
                common_messages.append({"role": "user", "content": message.content})
            elif message.role == ModelMessageRoleType.SYSTEM:
                system_messages.append(message.content)
            elif message.role == ModelMessageRoleType.AI:
                common_messages.append(
                    {"role": "assistant", "content": message.content}
                )
            else:
                pass
        return common_messages, system_messages


@dataclass
class ModelExtraMedata(BaseParameters):
    """A class to represent the extra metadata of a LLM."""

    prompt_roles: List[str] = field(
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
            "help": "The chat template, see: "
            "https://huggingface.co/docs/transformers/main/en/chat_templating"
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

    model: Union[str, List[str]] = field(
        metadata={"help": "Model name"},
    )
    label: Optional[str] = field(
        default=None,
        metadata={"help": "Model label"},
    )
    context_length: Optional[int] = field(
        default=None,
        metadata={"help": "Context length of model"},
    )
    max_output_length: Optional[int] = field(
        default=None,
        metadata={"help": "Max output length of model"},
    )
    description: Optional[str] = field(
        default=None,
        metadata={"help": "Model description"},
    )
    link: Optional[str] = field(
        default=None,
        metadata={"help": "Model link"},
    )
    chat_model: Optional[bool] = field(
        default=True,
        metadata={"help": "Whether the model is a chat model"},
    )
    function_calling: Optional[bool] = field(
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
        """Create a new model metadata from a dict."""
        if "ext_metadata" in data:
            data["ext_metadata"] = ModelExtraMedata(**data["ext_metadata"])
        return cls(**data)


class MessageConverter(ABC):
    r"""An abstract class for message converter.

    Different LLMs may have different message formats, this class is used to convert
    the messages to the format of the LLM.

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
        ...         # Convert the messages, merge system messages to the last user
        ...         # message.
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
        """Create a new default message converter."""
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

        3. Convert the messages to no system message if the model does not support
        system message

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
        if not model_metadata.ext_metadata.support_system_message:
            # 3. Convert the messages to no system message
            return self.convert_to_no_system_message(messages, model_metadata)
        return messages

    def convert_to_no_system_message(
        self,
        messages: List[ModelMessage],
        model_metadata: Optional[ModelMetadata] = None,
    ) -> List[ModelMessage]:
        r"""Convert the messages to no system message.

        Examples:
            >>> # Convert the messages to no system message, just merge system messages
            >>> # to the last user message
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
            ...         content="You are a helpful assistant\nWho are you",
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
                # Not support system message, append system message to the last user
                # message
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
            # Not support system messages, merge system messages to the last user
            #  message
            result_messages[-1].content = (
                system_message_str + prompt_sep + result_messages[-1].content
            )
        return result_messages

    def move_last_user_message_to_end(
        self, messages: List[ModelMessage]
    ) -> List[ModelMessage]:
        """Try to move the last user message to the end of the list.

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
        """Return the cache object to cache the model metadata.

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
        you can use the message converter to convert the messages to the format of the
        LLM.

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
        you can use the message converter to convert the messages to the format of the
        LLM.

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
        new_messages = message_converter.convert(request.get_messages(), model_metadata)
        new_request.messages = new_messages
        return new_request

    async def cached_models(self) -> List[ModelMetadata]:
        """Get all the models from the cache or the llm server.

        If the model metadata is not in the cache, it will be fetched from the
        llm server.

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

    def __call__(
        self, *args, **kwargs
    ) -> Coroutine[Any, Any, ModelOutput] | ModelOutput:
        """Return the model output.

        Call the LLM client to generate the response for the given message.

        Please do not use this method in the production environment, it is only used
        for debugging.
        """
        import asyncio

        from dbgpt.util import get_or_create_event_loop

        try:
            # Check if we are in an event loop
            loop = asyncio.get_running_loop()
            # If we are in an event loop, use async call
            if loop.is_running():
                # Because we are in an async environment, but this is a sync method,
                # we need to return a coroutine object for the caller to use await
                return self.async_call(*args, **kwargs)
            else:
                loop = get_or_create_event_loop()
                return loop.run_until_complete(self.async_call(*args, **kwargs))
        except RuntimeError:
            # If we are not in an event loop, use sync call
            loop = get_or_create_event_loop()
            return loop.run_until_complete(self.async_call(*args, **kwargs))

    async def async_call(self, *args, **kwargs) -> ModelOutput:
        """Return the model output asynchronously.

        Please do not use this method in the production environment, it is only used
        for debugging.
        """
        req = self._build_call_request(*args, **kwargs)
        return await self.generate(req)

    async def async_call_stream(self, *args, **kwargs) -> AsyncIterator[ModelOutput]:
        """Return the model output stream asynchronously.

        Please do not use this method in the production environment, it is only used
        for debugging.
        """
        req = self._build_call_request(*args, **kwargs)
        async for output in self.generate_stream(req):  # type: ignore
            yield output

    def _build_call_request(self, *args, **kwargs) -> ModelRequest:
        """Build the model request for the call method."""
        messages = kwargs.get("messages")
        model = kwargs.get("model")

        if messages:
            del kwargs["messages"]
            model_messages = ModelMessage.from_openai_messages(messages)
        else:
            model_messages = [ModelMessage.build_human_message(args[0])]

        if not model:
            if hasattr(self, "default_model"):
                model = getattr(self, "default_model")
            else:
                raise ValueError("The default model is not set")

        if "model" in kwargs:
            del kwargs["model"]

        return ModelRequest.build_request(model, model_messages, **kwargs)
