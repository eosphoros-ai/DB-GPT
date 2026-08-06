"""MacOS TTS Voice."""

import subprocess

from dbgpt.util.speech.base import VoiceBase


class MacOSTTS(VoiceBase):
    """MacOS TTS Voice."""

    def _setup(self) -> None:
        pass

    def _speech(self, text: str, voice_index: int = 0) -> bool:
        """Play the given text."""
        if voice_index == 0:
            args = ["say"]
        elif voice_index == 1:
            args = ["say", "-v", "Ava (Premium)"]
        else:
            args = ["say", "-v", "Samantha"]
        # Pass the text as a separate argument (no shell) so it cannot be
        # interpreted as a shell command, regardless of its content.
        subprocess.run([*args, text], check=False)
        return True
