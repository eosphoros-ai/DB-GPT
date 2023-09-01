from typing import List
from pilot.memory.chat_history.base import BaseChatHistoryMemory

from pilot.configs.config import Config
from pilot.scene.message import OnceConversation
from pilot.common.custom_data_structure import FixedSizeDict

CFG = Config()


class MemHistoryMemory(BaseChatHistoryMemory):
    histroies_map = FixedSizeDict(100)

    def __init__(self, chat_session_id: str):
        self.chat_seesion_id = chat_session_id
        self.histroies_map.update({chat_session_id: []})

    def messages(self) -> List[OnceConversation]:
        return self.histroies_map.get(self.chat_seesion_id)

    def append(self, once_message: OnceConversation) -> None:
        self.histroies_map.get(self.chat_seesion_id).append(once_message)

    def clear(self) -> None:
        self.histroies_map.pop(self.chat_seesion_id)
