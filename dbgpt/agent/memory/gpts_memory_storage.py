import dataclasses
from dataclasses import asdict, dataclass, fields
import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from dbgpt.core.interface.storage import (
    InMemoryStorage,
    QuerySpec,
    ResourceIdentifier,
    StorageInterface,
    StorageItem,
)
from dbgpt.agent.common.schema import Status
from datetime import datetime

from .base import GptsMessageMemory, GptsPlansMemory, GptsPlan, GptsMessage


@dataclass
class GptsPlanIdentifier(ResourceIdentifier):
    identifier_split: str = dataclasses.field(default="___$$$$___", init=False)
    conv_id: str
    sub_task_num: Optional[str]

    def __post_init__(self):
        if self.conv_id is None or self.sub_task_num is None:
            raise ValueError("conv_id and sub_task_num cannot be None")

        if any(
            self.identifier_split in key
            for key in [
                self.conv_id,
                self.sub_task_num,
            ]
            if key is not None
        ):
            raise ValueError(
                f"identifier_split {self.identifier_split} is not allowed in conv_id, sub_task_num"
            )

    @property
    def str_identifier(self) -> str:
        return self.identifier_split.join(
            key
            for key in [
                self.conv_id,
                self.sub_task_num,
            ]
            if key is not None
        )

    def to_dict(self) -> Dict:
        return {
            "conv_id": self.conv_id,
            "sub_task_num": self.sub_task_num,
        }


@dataclass
class GptsPlanStorage(StorageItem):
    """Gpts plan"""

    conv_id: str
    sub_task_num: int
    sub_task_content: Optional[str]
    sub_task_title: Optional[str] = None
    sub_task_agent: Optional[str] = None
    resource_name: Optional[str] = None
    rely: Optional[str] = None
    agent_model: Optional[str] = None
    retry_times: Optional[int] = 0
    max_retry_times: Optional[int] = 5
    state: Optional[str] = Status.TODO.value
    result: Optional[str] = None

    _identifier: GptsPlanIdentifier = dataclasses.field(init=False)

    @staticmethod
    def from_dict(d: Dict[str, Any]):
        return GptsPlanStorage(
            conv_id=d.get("conv_id"),
            sub_task_num=d["sub_task_num"],
            sub_task_content=d["sub_task_content"],
            sub_task_agent=d["sub_task_agent"],
            resource_name=d["resource_name"],
            rely=d["rely"],
            agent_model=d["agent_model"],
            retry_times=d["retry_times"],
            max_retry_times=d["max_retry_times"],
            state=d["state"],
            result=d["result"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def _check(self):
        if self.conv_id is None:
            raise ValueError("conv_id cannot be None")
        if self.sub_task_num is None:
            raise ValueError("sub_task_num cannot be None")
        if self.sub_task_content is None:
            raise ValueError("sub_task_content cannot be None")
        if self.state is None:
            raise ValueError("state cannot be None")

    @property
    def identifier(self) -> GptsPlanIdentifier:
        return self._identifier

    def merge(self, other: "StorageItem") -> None:
        """Merge the other item into the current item.

        Args:
            other (StorageItem): The other item to merge
        """
        if not isinstance(other, GptsPlanStorage):
            raise ValueError(
                f"Cannot merge {type(other)} into {type(self)} because they are not the same type."
            )
        self.from_object(other)


@dataclass
class GptsMessageIdentifier(ResourceIdentifier):
    identifier_split: str = dataclasses.field(default="___$$$$___", init=False)
    conv_id: str
    sender: Optional[str]
    receiver: Optional[str]
    rounds: Optional[int]

    def __post_init__(self):
        if (
            self.conv_id is None
            or self.sender is None
            or self.receiver is None
            or self.rounds is None
        ):
            raise ValueError("conv_id and sub_task_num cannot be None")

        if any(
            self.identifier_split in key
            for key in [
                self.conv_id,
                self.sender,
                self.receiver,
                self.rounds,
            ]
            if key is not None
        ):
            raise ValueError(
                f"identifier_split {self.identifier_split} is not allowed in conv_id, sender, receiver, rounds"
            )

    @property
    def str_identifier(self) -> str:
        return self.identifier_split.join(
            key
            for key in [
                self.conv_id,
                self.sender,
                self.receiver,
                self.rounds,
            ]
            if key is not None
        )

    def to_dict(self) -> Dict:
        return {
            "conv_id": self.conv_id,
            "sender": self.sender,
            "receiver": self.receiver,
            "rounds": self.rounds,
        }


@dataclass
class GptsMessageStorage(StorageItem):
    """Gpts Message"""

    conv_id: str
    sender: str

    receiver: str
    role: str
    content: str
    rounds: Optional[int]
    current_gogal: str = None
    context: Optional[str] = None
    review_info: Optional[str] = None
    action_report: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime = datetime.utcnow
    updated_at: datetime = datetime.utcnow

    _identifier: GptsMessageIdentifier = dataclasses.field(init=False)

    @staticmethod
    def from_dict(d: Dict[str, Any]):
        return GptsMessageStorage(
            conv_id=d["conv_id"],
            sender=d["sender"],
            receiver=d["receiver"],
            role=d["role"],
            content=d["content"],
            rounds=d["rounds"],
            model_name=d["model_name"],
            current_gogal=d["current_gogal"],
            context=d["context"],
            review_info=d["review_info"],
            action_report=d["action_report"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    def _check(self):
        if self.conv_id is None:
            raise ValueError("conv_id cannot be None")
        if self.sub_task_num is None:
            raise ValueError("sub_task_num cannot be None")
        if self.sub_task_content is None:
            raise ValueError("sub_task_content cannot be None")
        if self.state is None:
            raise ValueError("state cannot be None")

    def to_gpts_message(self) -> GptsMessage:
        """Convert the storage  to a GptsMessage."""
        input_variables = (
            None
            if not self.input_variables
            else self.input_variables.strip().split(",")
        )
        return GptsMessage(
            conv_id=self.conv_id,
            sender=self.sender,
            receiver=self.receiver,
            role=self.role,
            content=self.content,
            rounds=self.rounds,
            current_gogal=self.current_gogal,
            context=self.context,
            review_info=self.review_info,
            action_report=self.action_report,
            model_name=self.model_name,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @staticmethod
    def from_gpts_message(gpts_message: GptsMessage) -> "StoragePromptTemplate":
        """Convert a GptsMessage to a storage e."""
        return GptsMessageStorage(
            conv_id=gpts_message.conv_id,
            sender=gpts_message.sender,
            receiver=gpts_message.receiver,
            role=gpts_message.role,
            content=gpts_message.content,
            rounds=gpts_message.rounds,
            current_gogal=gpts_message.current_gogal,
            context=gpts_message.context,
            review_info=gpts_message.review_info,
            action_report=gpts_message.action_report,
            model_name=gpts_message.model_name,
            created_at=gpts_message.created_at,
            updated_at=gpts_message.updated_at,
        )

    @property
    def identifier(self) -> GptsMessageIdentifier:
        return self._identifier

    def merge(self, other: "StorageItem") -> None:
        """Merge the other item into the current item.

        Args:
            other (StorageItem): The other item to merge
        """
        if not isinstance(other, GptsMessageStorage):
            raise ValueError(
                f"Cannot merge {type(other)} into {type(self)} because they are not the same type."
            )
        self.from_object(other)


class GptsMessageManager(GptsMessageMemory):
    """The manager class for GptsMessage.

    Simple wrapper for the storage interface.

    """

    def __init__(self, storage: Optional[StorageInterface[GptsMessage, Any]] = None):
        if storage is None:
            storage = InMemoryStorage()
        self._storage = storage

    @property
    def storage(self) -> StorageInterface[GptsMessage, Any]:
        """The storage interface for prompt templates."""
        return self._storage

    def append(self, message: GptsMessage):
        self.storage.save(GptsMessageStorage.from_gpts_message(message))

    def get_by_agent(self, conv_id: str, agent: str) -> Optional[List[GptsMessage]]:
        query_spec = QuerySpec(
            conditions={
                "conv_id": conv_id,
                "sys_code": sys_code,
                **kwargs,
            }
        )
        queries: List[GptsMessageStorage] = self.storage.query(
            query_spec, GptsMessageStorage
        )
        if not queries:
            return []
        if prefer_prompt_language:
            prefer_prompt_language = prefer_prompt_language.lower()
            temp_queries = [
                query
                for query in queries
                if query.prompt_language
                and query.prompt_language.lower() == prefer_prompt_language
            ]
            if temp_queries:
                queries = temp_queries
        if prefer_model:
            prefer_model = prefer_model.lower()
            temp_queries = [
                query
                for query in queries
                if query.model and query.model.lower() == prefer_model
            ]
            if temp_queries:
                queries = temp_queries
        return queries

    def get_between_agents(
        self,
        conv_id: str,
        agent1: str,
        agent2: str,
        current_gogal: Optional[str] = None,
    ) -> Optional[List[GptsMessage]]:
        return super().get_between_agents(conv_id, agent1, agent2, current_gogal)

    def get_by_conv_id(self, conv_id: str) -> Optional[List[GptsMessage]]:
        return super().get_by_conv_id(conv_id)

    def get_last_message(self, conv_id: str) -> Optional[GptsMessage]:
        return super().get_last_message(conv_id)

    def prefer_query(
        self,
        prompt_name: str,
        sys_code: Optional[str] = None,
        prefer_prompt_language: Optional[str] = None,
        prefer_model: Optional[str] = None,
        **kwargs,
    ) -> List[GptsMessage]:
        """Query prompt templates from storage with prefer params.

        Sometimes, we want to query prompt templates with prefer params(e.g. some language or some model).
        This method will query prompt templates with prefer params first, if not found, will query all prompt templates.

        Examples:

            Query a prompt template.
            .. code-block:: python

                prompt_template_list = prompt_manager.prefer_query("hello")

            Query with sys_code and username.

            .. code-block:: python

                prompt_template_list = prompt_manager.prefer_query(
                    "hello", sys_code="sys_code", user_name="user_name"
                )

            Query with prefer prompt language.

            .. code-block:: python

                # First query with prompt name "hello" exactly.
                # Second filter with prompt language "zh-cn", if not found, will return all prompt templates.
                prompt_template_list = prompt_manager.prefer_query(
                    "hello", prefer_prompt_language="zh-cn"
                )

            Query with prefer model.

            .. code-block:: python

                # First query with prompt name "hello" exactly.
                # Second filter with model "vicuna-13b-v1.5", if not found, will return all prompt templates.
                prompt_template_list = prompt_manager.prefer_query(
                    "hello", prefer_model="vicuna-13b-v1.5"
                )

        Args:
            prompt_name (str): The name of the prompt template.
            sys_code (Optional[str], optional): The system code of the prompt template. Defaults to None.
            prefer_prompt_language (Optional[str], optional): The language of the prompt template. Defaults to None.
            prefer_model (Optional[str], optional): The model of the prompt template. Defaults to None.
            kwargs (Dict): Other query params(If some key and value not None, wo we query it exactly).
        """
        query_spec = QuerySpec(
            conditions={
                "prompt_name": prompt_name,
                "sys_code": sys_code,
                **kwargs,
            }
        )
        queries: List[StoragePromptTemplate] = self.storage.query(
            query_spec, StoragePromptTemplate
        )
        if not queries:
            return []
        if prefer_prompt_language:
            prefer_prompt_language = prefer_prompt_language.lower()
            temp_queries = [
                query
                for query in queries
                if query.prompt_language
                and query.prompt_language.lower() == prefer_prompt_language
            ]
            if temp_queries:
                queries = temp_queries
        if prefer_model:
            prefer_model = prefer_model.lower()
            temp_queries = [
                query
                for query in queries
                if query.model and query.model.lower() == prefer_model
            ]
            if temp_queries:
                queries = temp_queries
        return queries
