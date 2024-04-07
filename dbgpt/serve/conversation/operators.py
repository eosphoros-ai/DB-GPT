import logging
from typing import Any, Optional

from dbgpt.core import (
    BaseMessage,
    InMemoryStorage,
    MessageStorageItem,
    ModelRequest,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.awel.flow import IOField, OperatorCategory, ViewMetadata
from dbgpt.core.operators import PreChatHistoryLoadOperator
from dbgpt.util.i18n_utils import _

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
        super().__init__(
            storage, message_storage, use_in_memory_storage_if_not_set=False, **kwargs
        )

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


class DefaultServePreChatHistoryLoadOperator(ServePreChatHistoryLoadOperator):
    """Default pre-chat history load operator for DB-GPT serve component

    Use the storage and message storage of the serve component.
    """

    metadata = ViewMetadata(
        label=_("Default Chat History Load Operator"),
        name="default_serve_pre_chat_history_load_operator",
        category=OperatorCategory.CONVERSION,
        description=_(
            "Load chat history from the storage of the serve component."
            "It is the default storage of DB-GPT"
        ),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Model Request"),
                "model_request",
                type=ModelRequest,
                description=_("The model request."),
            )
        ],
        outputs=[
            IOField.build_from(
                label=_("Stored Messages"),
                name="output_value",
                type=BaseMessage,
                description=_("The messages stored in the storage."),
                is_list=True,
            )
        ],
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
