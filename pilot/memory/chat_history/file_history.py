from typing import List
import json
import os
import datetime
from pilot.memory.chat_history.base import BaseChatHistoryMemory
from pathlib import Path

from pilot.configs.config import Config
from pilot.scene.message import (
    OnceConversation,
    conversation_from_dict,
    conversations_to_dict,
)


CFG = Config()


class FileHistoryMemory(BaseChatHistoryMemory):
    def __init__(self, chat_session_id: str):
        now = datetime.datetime.now()
        date_string = now.strftime("%Y%m%d")
        path: str = f"{CFG.message_dir}/{date_string}"
        os.makedirs(path, exist_ok=True)

        dir_path = Path(path)
        self.file_path = Path(dir_path / f"{chat_session_id}.json")
        if not self.file_path.exists():
            self.file_path.touch()
            self.file_path.write_text(json.dumps([]))

    def messages(self) -> List[OnceConversation]:
        items = json.loads(self.file_path.read_text())
        history: List[OnceConversation] = []
        for onece in items:
            messages = conversation_from_dict(onece)
            history.append(messages)
        return history

    def append(self, once_message: OnceConversation) -> None:
        historys = self.messages()
        historys.append(once_message)
        self.file_path.write_text(
            json.dumps(conversations_to_dict(historys), ensure_ascii=False, indent=4),
            encoding="UTF-8",
        )

    def clear(self) -> None:
        self.file_path.write_text(json.dumps([]))
