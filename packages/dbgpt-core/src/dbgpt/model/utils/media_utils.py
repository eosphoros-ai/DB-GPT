import base64
import io
import os
from typing import Any, Dict, List, Sequence, Union

import numpy as np
import requests
import torch
from PIL import Image
from typing_extensions import Optional, TypedDict

from dbgpt.core.interface.media import MediaContent, MediaObject
from dbgpt.core.interface.message import ModelMessage

IMAGE_TYPE = Image.Image
VIDEO_TYPE = Union[torch.Tensor, list[Image.Image], np.ndarray]
AUDIO_TYPE = np.ndarray


class ParsedResults(TypedDict):
    images: Optional[List[IMAGE_TYPE]]
    """Parsed image data."""
    videos: Optional[Union[List[VIDEO_TYPE]]]
    """Parsed video data."""
    audios: Optional[List[AUDIO_TYPE]]
    """Parsed audio data."""
    ext_kwargs: Optional[Dict[str, Any]]


def parse_messages(messages: Sequence[ModelMessage]) -> ParsedResults:
    """Parse messages to extract media content."""
    images: List[MediaObject] = []
    videos: List[MediaObject] = []
    audios: List[MediaObject] = []
    for msg in messages:
        content = msg.content
        if isinstance(content, (list, dict)):
            media_content = MediaContent.parse_content(content)
            if not isinstance(media_content, list):
                media_content = [media_content]
            for media in media_content:
                if media.type == "image":
                    images.append(media.object)
                elif media.type == "video":
                    videos.append(media.object)
                elif media.type == "audio":
                    audios.append(media.object)

    batch_images = [_load_image(img) for img in images]
    batch_videos = [_load_video(video) for video in videos]
    batch_audio = [_load_audio(audio) for audio in audios]
    return ParsedResults(
        images=batch_images,
        videos=batch_videos,
        audios=batch_audio,
        ext_kwargs=None,
    )


def _load_image(image: MediaObject) -> Image.Image:
    """Load image from MediaObject.

    Args:
        image: MediaObject containing image data

    Returns:
        PIL.Image object

    Raises:
        ValueError: If the image format is not supported or the data cannot be processed
    """
    data = image.data
    format_info = image.format

    # Extract format type and media type if available
    format_parts = format_info.split("@", 1)
    format_type = format_parts[0]
    # media_type = format_parts[1] if len(format_parts) > 1 else None

    if format_type == "text":
        # Text is not a valid image format
        raise ValueError("Cannot load image from text format")

    elif format_type == "url":
        try:
            if isinstance(data, str):
                if data.startswith(("http://", "https://")):
                    response = requests.get(data, stream=True)
                    response.raise_for_status()
                    return Image.open(io.BytesIO(response.content))
                elif os.path.exists(data):
                    return Image.open(data)
                else:
                    raise ValueError(
                        "URL neither starts with http/https nor points to an existing "
                        f"local file: {data}"
                    )
            else:
                raise ValueError("URL format requires string data")
        except Exception as e:
            raise ValueError(f"Failed to load image from URL: {e}")

    elif format_type == "base64":
        try:
            # Remove data URI prefix if present (e.g., "data:image/jpeg;base64,")
            if isinstance(data, str) and "," in data:
                data = data.split(",", 1)[1]

            # Decode base64 data
            image_data = base64.b64decode(data)
            return Image.open(io.BytesIO(image_data))
        except Exception as e:
            raise ValueError(f"Failed to decode base64 image: {e}")

    elif format_type == "binary":
        try:
            if not isinstance(data, bytes):
                raise ValueError("Binary format requires bytes data")
            return Image.open(io.BytesIO(data))
        except Exception as e:
            raise ValueError(f"Failed to load binary image: {e}")

    else:
        raise ValueError(f"Unsupported image format: {format_type}")


def _load_video(
    video: MediaObject,
) -> Union[torch.Tensor, list[Image.Image], np.ndarray]:
    """Load video from MediaObject by creating a temporary file and using
    transformers.image_utils.load_video.

    Args:
        video: MediaObject containing video data

    Returns:
        Video data as torch.Tensor, list of PIL.Image, or numpy.ndarray

    Raises:
        ValueError: If the video format is not supported or the data cannot be processed
    """
    import os
    import tempfile

    from transformers.image_utils import load_video

    data = video.data
    format_info = video.format

    # Extract format type and media type if available
    format_parts = format_info.split("@", 1)
    format_type = format_parts[0]
    # media_type = format_parts[1] if len(format_parts) > 1 else None

    if (
        format_type == "url"
        and isinstance(data, str)
        and (data.startswith(("http://", "https://")) or os.path.isfile(data))
    ):
        try:
            video_data, metadata = load_video(data)
            return video_data
        except Exception as e:
            raise ValueError(f"Failed to load video from URL using transformers: {e}")

    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, f"temp_video_{id(data)}.mp4")

    try:
        if format_type == "text":
            raise ValueError("Cannot load video from text format")

        elif format_type == "url":
            raise ValueError("Unsupported URL format for video data")

        elif format_type == "base64":
            # Handle base64-encoded video data
            if isinstance(data, str):
                # Remove data URI prefix if present (e.g., "data:video/mp4;base64,")
                if "," in data:
                    data = data.split(",", 1)[1]

                # Decode base64 data
                video_data = base64.b64decode(data)
                # Save to temporary file
                with open(temp_file_path, "wb") as f:
                    f.write(video_data)
            else:
                raise ValueError("Base64 format requires string data")

        elif format_type == "binary":
            # Handle binary video data
            if not isinstance(data, bytes):
                raise ValueError("Binary format requires bytes data")

            # Save to temporary file
            with open(temp_file_path, "wb") as f:
                f.write(data)

        else:
            raise ValueError(f"Unsupported video format: {format_type}")

        # Use transformers' load_video to load the video
        video_data, metadata = load_video(temp_file_path)
        return video_data

    except Exception as e:
        raise ValueError(f"Failed to load video: {e}")

    finally:
        # Remove the temporary file and directory
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)


def _load_audio(audio: MediaObject, sr: int = 16000) -> np.ndarray:
    """Load audio from MediaObject using librosa.

    Args:
        audio: MediaObject containing audio data
        sr: Sample rate for librosa (default is 16000)

    Returns:
        Audio data as numpy.ndarray

    Raises:
        ValueError: If the audio format is not supported or the data cannot be processed
    """
    from io import BytesIO

    import audioread
    import librosa

    data = audio.data
    format_info = audio.format

    # Extract format type and media type if available
    format_parts = format_info.split("@", 1)
    format_type = format_parts[0]
    # media_type = format_parts[1] if len(format_parts) > 1 else None

    if format_type == "text":
        raise ValueError("Cannot load audio from text format")

    elif format_type == "url":
        try:
            if isinstance(data, str):
                if data.startswith(("http://", "https://")):
                    # Use audioread.ffdec.FFmpegAudioFile to handle network audio
                    return librosa.load(audioread.ffdec.FFmpegAudioFile(data), sr=sr)[0]
                elif data.startswith("file://"):
                    return librosa.load(data[len("file://") :], sr=sr)[0]
                elif os.path.exists(data):
                    return librosa.load(data, sr=sr)[0]
                else:
                    raise ValueError(
                        "URL neither starts with http/https nor points to an existing "
                        f"local file: {data}"
                    )
            else:
                raise ValueError("URL format requires string data")
        except Exception as e:
            raise ValueError(f"Failed to load audio from URL: {e}")

    elif format_type == "base64":
        try:
            # Handle base64-encoded audio data
            if isinstance(data, str):
                if data.startswith("data:audio") and "base64," in data:
                    _, base64_data = data.split("base64,", 1)
                    data = base64_data

                decoded_data = base64.b64decode(data)
                return librosa.load(BytesIO(decoded_data), sr=sr)[0]
            else:
                raise ValueError("Base64 format requires string data")
        except Exception as e:
            raise ValueError(f"Failed to decode base64 audio: {e}")

    elif format_type == "binary":
        try:
            if not isinstance(data, bytes):
                raise ValueError("Binary format requires bytes data")

            temp_file = f"temp_audio_{id(data)}"
            try:
                with open(temp_file, "wb") as f:
                    f.write(data)
                audio_array = librosa.load(temp_file, sr=sr)[0]
                return audio_array
            finally:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        except Exception as e:
            raise ValueError(f"Failed to load binary audio: {e}")

    else:
        raise ValueError(f"Unsupported audio format: {format_type}")
