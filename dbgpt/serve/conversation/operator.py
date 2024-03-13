import logging
from typing import Any, Optional

from dbgpt.core import (
    InMemoryStorage,
    MessageStorageItem,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.operators import PreChatHistoryLoadOperator

from .serve import Serve

logger = logging.getLogger(__name__)


class ServePreChatHistoryLoadOperator(PreChatHistoryLoadOperator):
    """Pre-chat history load operator for DB-GPT serve component

    Args:
        storage (Optional[StorageInterface[StorageConversation, Any]], optional):
            The conversation storage, store the conversation items. Defaults to None.
        message_storage (Optional[StorageInterface[MessageStorageItem, Any]], optional):
            The message storage, store the messages of one conversation. Defaults to None.

    If the storage or message_storage is not None, the storage or message_storage will be used first.
    Otherwise, we will try get current serve component from system app,
    and use the storage or message_storage of the serve component.
    If we can't get the storage, we will use the InMemoryStorage as the storage or message_storage.
    """

    def __init__(
        self,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
        **kwargs,
    ):
        super().__init__(storage, message_storage, **kwargs)

    @property
    def storage(self):
        if self._storage:
            return self._storage
        storage = Serve.call_on_current_serve(
            self.system_app, lambda serve: serve.conv_storage
        )
        if not storage:
            logger.warning(
                "Can't get the conversation storage from current serve component, "
                "use the InMemoryStorage as the conversation storage."
            )
            self._storage = InMemoryStorage()
            return self._storage
        return storage

    @property
    def message_storage(self):
        if self._message_storage:
            return self._message_storage
        storage = Serve.call_on_current_serve(
            self.system_app,
            lambda serve: serve.message_storage,
        )
        if not storage:
            logger.warning(
                "Can't get the message storage from current serve component, "
                "use the InMemoryStorage as the message storage."
            )
            self._message_storage = InMemoryStorage()
            return self._message_storage
        return storage
