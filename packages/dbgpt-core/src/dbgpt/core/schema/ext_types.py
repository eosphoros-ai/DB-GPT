"""Extended types for the OpenAI API."""

from typing_extensions import Literal, Required, TypedDict


class ExtAudioURL(TypedDict, total=False):
    url: Required[str]
    """URL of the audio file."""

    detail: Required[Literal["wav", "mp3"]]
    """The format of the encoded audio data."""


class ExtChatCompletionContentPartInputAudioParam(TypedDict, total=False):
    audio_url: Required[ExtAudioURL]

    type: Required[Literal["audio_url"]]
    """The type of the content part. Always `audio_url`."""


class ExtVideoURL(TypedDict, total=False):
    url: Required[str]
    """URL of the video file."""

    detail: Required[Literal["mp4", "avi"]]
    """The format of the encoded video data."""


class ExtChatCompletionContentPartInputVideoParam(TypedDict, total=False):
    video_url: Required[ExtVideoURL]

    type: Required[Literal["video_url"]]
    """The type of the content part. Always `video_url`."""


class ExtFileURL(TypedDict, total=False):
    url: Required[str]
    """URL of the file."""


class ExtChatCompletionContentPartInputFileParam(TypedDict, total=False):
    file_url: Required[ExtFileURL]
    type: Required[Literal["file_url"]]
    """The type of the content part. Always `file_url`."""
