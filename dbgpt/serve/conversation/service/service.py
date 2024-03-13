from typing import Any, Dict, List, Optional, Union

from dbgpt.component import BaseComponent, SystemApp
from dbgpt.core import (
    InMemoryStorage,
    MessageStorageItem,
    QuerySpec,
    StorageConversation,
    StorageInterface,
)
from dbgpt.core.interface.message import _append_view_messages
from dbgpt.serve.core import BaseService
from dbgpt.storage.metadata import BaseDao
from dbgpt.storage.metadata._base_dao import REQ, RES
from dbgpt.util.pagination_utils import PaginationResult

from ..api.schemas import MessageVo, ServeRequest, ServerResponse
from ..config import SERVE_CONFIG_KEY_PREFIX, SERVE_SERVICE_COMPONENT_NAME, ServeConfig
from ..models.models import ServeDao, ServeEntity


class Service(BaseService[ServeEntity, ServeRequest, ServerResponse]):
    """The service class for Conversation"""

    name = SERVE_SERVICE_COMPONENT_NAME

    def __init__(
        self,
        system_app: SystemApp,
        dao: Optional[ServeDao] = None,
        storage: Optional[StorageInterface[StorageConversation, Any]] = None,
        message_storage: Optional[StorageInterface[MessageStorageItem, Any]] = None,
    ):
        self._system_app = None
        self._serve_config: ServeConfig = None
        self._dao: ServeDao = dao
        self._storage = storage
        self._message_storage = message_storage
        super().__init__(system_app)

    def init_app(self, system_app: SystemApp) -> None:
        """Initialize the service

        Args:
            system_app (SystemApp): The system app
        """
        self._serve_config = ServeConfig.from_app_config(
            system_app.config, SERVE_CONFIG_KEY_PREFIX
        )
        self._dao = self._dao or ServeDao(self._serve_config)
        self._system_app = system_app

    @property
    def dao(self) -> ServeDao:
        """Returns the internal DAO."""
        return self._dao

    @property
    def config(self) -> ServeConfig:
        """Returns the internal ServeConfig."""
        return self._serve_config

    def create(self, request: REQ) -> RES:
        raise NotImplementedError()

    @property
    def conv_storage(self) -> StorageInterface:
        """The conversation storage, store the conversation items."""
        if self._storage:
            return self._storage
        from ..serve import Serve

        return Serve.call_on_current_serve(
            self._system_app, lambda serve: serve.conv_storage
        )

    @property
    def message_storage(self) -> StorageInterface:
        """The message storage, store the messages of one conversation."""
        if self._message_storage:
            return self._message_storage
        from ..serve import Serve

        return Serve.call_on_current_serve(
            self._system_app,
            lambda serve: serve.message_storage,
        )

    def create_storage_conv(
        self, request: Union[ServeRequest, Dict[str, Any]], load_message: bool = True
    ) -> StorageConversation:
        conv_storage = self.conv_storage
        message_storage = self.message_storage
        if not conv_storage or not message_storage:
            raise RuntimeError(
                "Can't get the conversation storage or message storage from current serve component."
            )
        if isinstance(request, dict):
            request = ServeRequest(**request)
        storage_conv: StorageConversation = StorageConversation(
            conv_uid=request.conv_uid,
            chat_mode=request.chat_mode,
            user_name=request.user_name,
            sys_code=request.sys_code,
            conv_storage=conv_storage,
            message_storage=message_storage,
            load_message=load_message,
        )
        return storage_conv

    def update(self, request: ServeRequest) -> ServerResponse:
        """Update a Conversation entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = {
            # "id": request.id
        }
        return self.dao.update(query_request, update_request=request)

    def get(self, request: ServeRequest) -> Optional[ServerResponse]:
        """Get a Conversation entity

        Args:
            request (ServeRequest): The request

        Returns:
            ServerResponse: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self.dao.get_one(query_request)

    def delete(self, request: ServeRequest) -> None:
        """Delete current conversation and its messages

        Args:
            request (ServeRequest): The request
        """
        conv: StorageConversation = self.create_storage_conv(request)
        conv.delete()

    def get_list(self, request: ServeRequest) -> List[ServerResponse]:
        """Get a list of Conversation entities

        Args:
            request (ServeRequest): The request

        Returns:
            List[ServerResponse]: The response
        """
        # TODO: implement your own logic here
        # Build the query request from the request
        query_request = request
        return self.dao.get_list(query_request)

    def get_list_by_page(
        self, request: ServeRequest, page: int, page_size: int
    ) -> PaginationResult[ServerResponse]:
        """Get a list of Conversation entities by page

        Args:
            request (ServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[ServerResponse]: The response
        """
        return self.dao.get_conv_by_page(request, page, page_size)

    def get_history_messages(
        self, request: Union[ServeRequest, Dict[str, Any]]
    ) -> List[MessageVo]:
        """Get a list of Conversation entities

        Args:
            request (ServeRequest): The request

        Returns:
            List[ServerResponse]: The response
        """
        conv: StorageConversation = self.create_storage_conv(request)
        result = []
        messages = _append_view_messages(conv.messages)
        for msg in messages:
            result.append(
                MessageVo(
                    role=msg.type,
                    context=msg.content,
                    order=msg.round_index,
                    model_name=self.config.default_model,
                )
            )
        return result
