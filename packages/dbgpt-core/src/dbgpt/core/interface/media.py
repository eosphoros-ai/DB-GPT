from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional, Union

from dbgpt.core.schema.types import (
    ChatCompletionContentPartParam,
    ChatCompletionMessageParam,
)
from dbgpt.util.i18n_utils import _

MEDIA_DATA_TYPE = Union[str, bytes]
MEDIA_DATA_FORMAT_TYPE = Literal[
    "text",
    "url",
    "base64",
    "binary",
]


@dataclass
class MediaObject:
    """Media object for the model output or model request."""

    data: MEDIA_DATA_TYPE = field(metadata={"help": _("The media data")})
    format: MEDIA_DATA_FORMAT_TYPE = field(
        default="text", metadata={"help": _("The format of the media")}
    )


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

    @classmethod
    def parse_content(
        cls,
        content: Union[
            "MediaContent", List["MediaContent"], Dict[str, Any], List[Dict[str, Any]]
        ],
    ) -> Union["MediaContent", List["MediaContent"]]:
        def _parse_dict(obj_dict: Union[MediaContent, Dict[str, Any]]) -> MediaContent:
            if isinstance(obj_dict, MediaContent):
                return obj_dict
            content_object = obj_dict.get("object")
            if not content_object:
                raise ValueError(f"Failed to parse {obj_dict}, no object found")
            if isinstance(content_object, dict):
                content_object = MediaObject(
                    data=content_object.get("data"),
                    format=content_object.get("format", "text"),
                )
            return cls(
                type=obj_dict.get("type", "text"),
                object=content_object,
            )

        if isinstance(content, list):
            return [_parse_dict(c) for c in content]
        else:
            return _parse_dict(content)

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

    @classmethod
    def last_text(cls, contents: List["MediaContent"]) -> str:
        """Get the last text from the contents."""
        if not contents:
            raise ValueError("The contents are empty")
        for content in reversed(contents):
            if content.type == MediaContentType.TEXT:
                return content.get_text()
        raise ValueError("No text content found")

    @classmethod
    def parse_chat_completion_message(
        cls,
        message: Union[str, ChatCompletionMessageParam],
        ignore_unknown_media: bool = False,
    ) -> Union["MediaContent", List["MediaContent"]]:
        """Parse the chat completion message."""
        if not message:
            raise ValueError("The message is empty")
        if isinstance(message, str):
            return cls.build_text(message)
        content = message.get("content")
        if not content:
            raise ValueError(f"Failed to parse {message}, no content found")
        if not isinstance(content, Iterable):
            raise ValueError(f"Failed to parse {message}, content is not iterable")
        result = []
        for item in content:
            if isinstance(item, str):
                result.append(cls.build_text(item))
            elif isinstance(item, dict) and "type" in item:
                type = item["type"]
                if type == "text" and "text" in item:
                    result.append(cls.build_text(item["text"]))
                elif type == "image_url" and "image_url" in item:
                    result.append(
                        cls(
                            type="image",
                            object=MediaObject(
                                data=item["image_url"]["url"],
                                format="url",
                            ),
                        )
                    )
                elif type == "input_audio" and "input_audio" in item:
                    result.append(
                        cls(
                            type="audio",
                            object=MediaObject(
                                data=item["input_audio"]["data"],
                                format="base64",
                            ),
                        )
                    )
                else:
                    if not ignore_unknown_media:
                        raise ValueError(
                            f"Unknown message type: {item} of system message"
                        )
            else:
                raise ValueError(f"Unknown message type: {item} of system message")
        return result

    @classmethod
    def to_chat_completion_message(
        cls,
        role,
        content: Union[str, "MediaContent", List["MediaContent"]],
        support_media_content: bool = True,
        type_mapping: Optional[Dict[str, str]] = None,
    ) -> ChatCompletionMessageParam:
        """Convert the media contents to chat completion message."""
        if not content:
            raise ValueError("The content are empty")
        if isinstance(content, str):
            return {"role": role, "content": content}
        if isinstance(content, MediaContent):
            content = [content]
        new_content = [
            cls._parse_single_media_content(c, type_mapping=type_mapping)
            for c in content
        ]
        if not support_media_content:
            text_content = [
                c["text"] for c in new_content if c["type"] == "text" and "text" in c
            ]
            if not text_content:
                raise ValueError("No text content found in the media contents")
            # Not support media content, just pass the string text as content
            new_content = text_content[0]
        return {
            "role": role,
            "content": new_content,
        }

    @classmethod
    def _parse_single_media_content(
        cls,
        content: "MediaContent",
        type_mapping: Optional[Dict[str, str]] = None,
    ) -> ChatCompletionContentPartParam:
        """Parse a single content."""
        if type_mapping is None:
            type_mapping = {}
        if content.type == MediaContentType.TEXT:
            real_type = type_mapping.get("text", "text")
            return {
                real_type: str(content.object.data),
                "type": real_type,
            }
        elif content.type == MediaContentType.IMAGE:
            if content.object.format.startswith("url"):
                # Compatibility for most image url formats
                real_type = type_mapping.get("image_url", "image_url")
                if real_type == "image_url":
                    return {
                        "image_url": {
                            "url": content.object.data,
                        },
                        "type": "image_url",
                    }
                else:
                    return {
                        real_type: content.object.data,
                        "type": real_type,
                    }
            else:
                raise ValueError(f"Unsupported image format: {content.object.format}")
        elif content.type == MediaContentType.AUDIO:
            if content.object.format.startswith("base64"):
                real_type = type_mapping.get("input_audio", "input_audio")
                return {
                    real_type: {
                        "data": content.object.data,
                    },
                    "type": real_type,
                }
            else:
                raise ValueError(f"Unsupported audio format: {content.object.format}")
        elif content.type == MediaContentType.VIDEO:
            if content.object.format.startswith("url"):
                real_type = type_mapping.get("video_url", "video_url")
                return {
                    real_type: {
                        "url": content.object.data,
                    },
                    "type": real_type,
                }
            else:
                raise ValueError(f"Unsupported video format: {content.object.format}")
        else:
            raise ValueError(f"Unsupported content type: {content.type}")

    @classmethod
    def get_view_markdown_text(
        cls,
        media_contents: List["MediaContent"],
        replace_url_func: Callable[[str], str],
    ) -> str:
        texts = []
        media = []
        for content in media_contents:
            if content.type == MediaContentType.TEXT:
                texts.append(content.get_text())
            elif content.type == MediaContentType.IMAGE:
                if content.object.format.startswith("url"):
                    media.append(f"![image]({replace_url_func(content.object.data)})")
                else:
                    raise ValueError(
                        f"Unsupported image format: {content.object.format}"
                    )
            elif content.type == MediaContentType.AUDIO:
                if content.object.format.startswith("base64"):
                    media.append(f"[audio](data:{content.object.data})")
                else:
                    raise ValueError(
                        f"Unsupported audio format: {content.object.format}"
                    )
            elif content.type == MediaContentType.VIDEO:
                if content.object.format.startswith("url"):
                    media.append(f"[video]({replace_url_func(content.object.data)})")
                else:
                    raise ValueError(
                        f"Unsupported video format: {content.object.format}"
                    )
        res = ""
        if texts:
            res += "\n".join(texts)
        if media:
            res += "\n" + "\n".join(media)
        return res

    @classmethod
    def apply_func(
        cls,
        media_contents: List["MediaContent"],
        func: Callable[[MediaObject], MediaObject],
    ) -> List["MediaContent"]:
        """Apply a function to the media contents."""
        if not media_contents:
            raise ValueError("The media contents are empty")
        return [
            cls(type=content.type, object=func(content.object))
            for content in media_contents
        ]

    @classmethod
    def replace_url(
        cls,
        media_contents: List["MediaContent"],
        replace_func: Callable[[str], str],
    ) -> List["MediaContent"]:
        """Replace the url in the media contents."""
        if not media_contents:
            raise ValueError("The media contents are empty")

        def _func(obj: MediaObject) -> MediaObject:
            if obj.format.startswith("url"):
                data = replace_func(obj.data)
            else:
                data = obj.data
            return MediaObject(
                data=data,
                format=obj.format,
            )

        return cls.apply_func(media_contents, _func)


class MediaProcessor(ABC):
    """Media processor for the model output or model request."""

    @abstractmethod
    def process(self, content: MediaContent) -> MediaContent:
        """Process the media content."""

    def batch_process(self, contents: List[MediaContent]) -> List[MediaContent]:
        """Batch process the media content."""
        return [self.process(content) for content in contents]
