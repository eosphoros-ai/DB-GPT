from typing import List
from dbgpt.storage.chat_history.base import BaseChatHistoryMemory

from dbgpt._private.config import Config
from dbgpt.core.interface.message import OnceConversation
from dbgpt.util.custom_data_structure import FixedSizeDict
from dbgpt.storage.chat_history.base import MemoryStoreType

CFG = Config()


class MemHistoryMemory(BaseChatHistoryMemory):
    store_type: str = MemoryStoreType.Memory.value

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
