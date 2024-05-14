""" Text to speech module """
import threading
from threading import Semaphore

from dbgpt._private.config import Config
from dbgpt.util.speech.base import VoiceBase
from dbgpt.util.speech.brian import BrianSpeech
from dbgpt.util.speech.eleven_labs import ElevenLabsSpeech
from dbgpt.util.speech.gtts import GTTSVoice
from dbgpt.util.speech.macos_tts import MacOSTTS

_QUEUE_SEMAPHORE = Semaphore(
    1
)  # The amount of sounds to queue before blocking the main thread


def say_text(text: str, voice_index: int = 0) -> None:
    """Speak the given text using the given voice index"""
    cfg = Config()
    default_voice_engine, voice_engine = _get_voice_engine(cfg)

    def speak() -> None:
        success = voice_engine.say(text, voice_index)
        if not success:
            default_voice_engine.say(text)

        _QUEUE_SEMAPHORE.release()

    _QUEUE_SEMAPHORE.acquire(True)
    thread = threading.Thread(target=speak)
    thread.start()


def _get_voice_engine(config: Config) -> tuple[VoiceBase, VoiceBase]:
    """Get the voice engine to use for the given configuration"""
    default_voice_engine = GTTSVoice()
    if config.elevenlabs_api_key:
        voice_engine = ElevenLabsSpeech()
    elif config.use_mac_os_tts:
        voice_engine = MacOSTTS()
    elif config.use_brian_tts == "True":
        voice_engine = BrianSpeech()
    else:
        voice_engine = GTTSVoice()

    return default_voice_engine, voice_engine
