"""This is an auto-generated model file
You can define your own models and DAOs here
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from dbgpt.core import MessageStorageItem
from dbgpt.storage.chat_history.chat_history_db import ChatHistoryEntity as ServeEntity
from dbgpt.storage.chat_history.chat_history_db import ChatHistoryMessageEntity
from dbgpt.storage.metadata import BaseDao, Model, db
from dbgpt.util import PaginationResult

from ..api.schemas import ServeRequest, ServerResponse
from ..config import SERVER_APP_TABLE_NAME, ServeConfig


class ServeDao(BaseDao[ServeEntity, ServeRequest, ServerResponse]):
    """The DAO class for Conversation"""

    def __init__(self, serve_config: ServeConfig):
        super().__init__()
        self._serve_config = serve_config

    def from_request(self, request: Union[ServeRequest, Dict[str, Any]]) -> ServeEntity:
        """Convert the request to an entity

        Args:
            request (Union[ServeRequest, Dict[str, Any]]): The request

        Returns:
            T: The entity
        """
        request_dict = request.dict() if isinstance(request, ServeRequest) else request
        entity = ServeEntity(**request_dict)
        # TODO implement your own logic here, transfer the request_dict to an entity
        return entity

    def to_request(self, entity: ServeEntity) -> ServeRequest:
        """Convert the entity to a request

        Args:
            entity (T): The entity

        Returns:
            REQ: The request
        """
        # TODO implement your own logic here, transfer the entity to a request
        return ServeRequest()

    def to_response(self, entity: ServeEntity) -> ServerResponse:
        """Convert the entity to a response

        Args:
            entity (T): The entity

        Returns:
            RES: The response
        """
        # TODO implement your own logic here, transfer the entity to a response
        return ServerResponse(
            conv_uid=entity.conv_uid,
            user_input=entity.summary,
            chat_mode=entity.chat_mode,
            user_name=entity.user_name,
            sys_code=entity.sys_code,
        )

    def get_latest_message(self, conv_uid: str) -> Optional[MessageStorageItem]:
        """Get the latest message of a conversation

        Args:
            conv_uid (str): The conversation UID

        Returns:
            ChatHistoryMessageEntity: The latest message
        """
        with self.session() as session:
            entity: ChatHistoryMessageEntity = (
                session.query(ChatHistoryMessageEntity)
                .filter(ChatHistoryMessageEntity.conv_uid == conv_uid)
                .order_by(ChatHistoryMessageEntity.gmt_created.desc())
                .first()
            )
            if not entity:
                return None
            message_detail = (
                json.loads(entity.message_detail) if entity.message_detail else {}
            )
            return MessageStorageItem(entity.conv_uid, entity.index, message_detail)

    def _parse_old_messages(self, entity: ServeEntity) -> List[Dict[str, Any]]:
        """Parse the old messages

        Args:
            entity (ServeEntity): The entity

        Returns:
            str: The old messages
        """
        messages = json.loads(entity.messages)
        return messages

    def get_conv_by_page(
        self, req: ServeRequest, page: int, page_size: int
    ) -> PaginationResult[ServerResponse]:
        """Get conversation by page

        Args:
            req (ServeRequest): The request
            page (int): The page number
            page_size (int): The page size

        Returns:
            List[ChatHistoryEntity]: The conversation list
        """
        with self.session(commit=False) as session:
            query = self._create_query_object(session, req)
            query = query.order_by(ServeEntity.gmt_created.desc())
            total_count = query.count()
            items = query.offset((page - 1) * page_size).limit(page_size)
            total_pages = (total_count + page_size - 1) // page_size
            result_items = []
            for item in items:
                select_param, model_name = "", None
                if item.messages:
                    messages = self._parse_old_messages(item)
                    last_round = max(messages, key=lambda x: x["chat_order"])
                    if "param_value" in last_round:
                        select_param = last_round["param_value"]
                    else:
                        select_param = ""
                else:
                    latest_message = self.get_latest_message(item.conv_uid)
                    if latest_message:
                        message = latest_message.to_message()
                        select_param = message.additional_kwargs.get("param_value")
                        model_name = message.additional_kwargs.get("model_name")
                res_item = self.to_response(item)
                res_item.select_param = select_param
                res_item.model_name = model_name
                result_items.append(res_item)

            result = PaginationResult(
                items=result_items,
                total_count=total_count,
                total_pages=total_pages,
                page=page,
                page_size=page_size,
            )

        return result
