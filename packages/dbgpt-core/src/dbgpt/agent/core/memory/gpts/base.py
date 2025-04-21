"""Gpts memory define."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...schema import Status


@dataclasses.dataclass
class GptsPlan:
    """Gpts plan."""

    conv_id: str
    conv_round: int
    sub_task_id: str
    sub_task_num: int
    task_uid: str
    sub_task_content: Optional[str]
    task_parent: Optional[str] = None
    conv_round_id: Optional[str] = None
    sub_task_title: Optional[str] = None
    sub_task_agent: Optional[str] = None
    resource_name: Optional[str] = None
    agent_model: Optional[str] = None
    retry_times: int = 0
    max_retry_times: int = 5
    state: Optional[str] = Status.TODO.value
    action: Optional[str] = None
    action_input: Optional[str] = None
    result: Optional[str] = None

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "GptsPlan":
        """Create a GptsPlan object from a dictionary."""
        return GptsPlan(
            conv_id=d["conv_id"],
            conv_round=d["conv_id"],
            task_uid=d["task_uid"],
            sub_task_num=d["sub_task_num"],
            sub_task_id=d["sub_task_id"],
            conv_round_id=d.get("conv_round_id"),
            task_parent=d.get("task_parent"),
            sub_task_content=d["sub_task_content"],
            sub_task_agent=d["sub_task_agent"],
            resource_name=d["resource_name"],
            agent_model=d["agent_model"],
            retry_times=d["retry_times"],
            max_retry_times=d["max_retry_times"],
            state=d["state"],
            result=d["result"],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the GptsPlan object."""
        return dataclasses.asdict(self)


@dataclasses.dataclass
class GptsMessage:
    """Gpts message."""

    conv_id: str
    sender: str
    sender_name: str
    message_id: str
    receiver: str
    receiver_name: str
    role: str
    content: str
    rounds: int = 0
    is_success: bool = True
    avatar: Optional[str] = None
    thinking: Optional[str] = None
    app_code: Optional[str] = None
    app_name: Optional[str] = None
    current_goal: Optional[str] = None
    context: Optional[str] = None
    review_info: Optional[str] = None
    action_report: Optional[str] = None
    model_name: Optional[str] = None
    resource_info: Optional[str] = None
    show_message: bool = True
    created_at: datetime = dataclasses.field(default_factory=datetime.utcnow)
    updated_at: datetime = dataclasses.field(default_factory=datetime.utcnow)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "GptsMessage":
        """Create a GptsMessage object from a dictionary."""
        return GptsMessage(
            conv_id=d["conv_id"],
            message_id=d["message_id"],
            sender=d["sender"],
            sender_name=d["sender_name"],
            receiver=d["receiver"],
            receiver_name=d["receiver_name"],
            role=d["role"],
            avatar=d.get("avatar"),
            thinking=d["thinking"],
            content=d["content"],
            rounds=d["rounds"],
            is_success=d["is_success"],
            app_code=d["app_code"],
            app_name=d["app_name"],
            model_name=d["model_name"],
            current_goal=d["current_goal"],
            context=d["context"],
            review_info=d["review_info"],
            action_report=d["action_report"],
            resource_info=d["resource_info"],
            show_message=d["show_message"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the GptsMessage object."""
        return dataclasses.asdict(self)


class GptsPlansMemory(ABC):
    """Gpts plans memory interface."""

    @abstractmethod
    def batch_save(self, plans: List[GptsPlan]) -> None:
        """Save plans in batch.

        Args:
            plans: panner generate plans info

        """

    @abstractmethod
    def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        """Get plans by conv_id.

        Args:
            conv_id: conversation id

        Returns:
            List[GptsPlan]: List of planning steps
        """

    @abstractmethod
    def get_by_conv_id_and_num(
        self, conv_id: str, task_ids: List[str]
    ) -> List[GptsPlan]:
        """Get plans by conv_id and task number.

        Args:
            conv_id(str): conversation id
            task_ids(List[int]): List of sequence numbers of plans in the same
                conversation

        Returns:
            List[GptsPlan]: List of planning steps
        """

    @abstractmethod
    def get_todo_plans(self, conv_id: str) -> List[GptsPlan]:
        """Get unfinished planning steps.

        Args:
            conv_id(str): Conversation id

        Returns:
            List[GptsPlan]: List of planning steps
        """

    @abstractmethod
    def get_plans_by_msg_round(self, conv_id: str, rounds_id: str) -> List[GptsPlan]:
        """Get unfinished planning steps.

        Args:
            conv_id(str): Conversation id
            rounds_id(str): rounds id
        Returns:
            List[GptsPlan]: List of planning steps
        """

    @abstractmethod
    def complete_task(self, conv_id: str, task_id: str, result: str) -> None:
        """Set the planning step to complete.

        Args:
            conv_id(str): conversation id
            task_id(str): Planning step id
            result(str): Plan step results
        """

    @abstractmethod
    def update_task(
        self,
        conv_id: str,
        task_id: str,
        state: str,
        retry_times: int,
        agent: Optional[str] = None,
        model: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        """Update planning step information.

        Args:
            conv_id(str): conversation id
            task_id(str): Planning step num
            state(str): the status to update to
            retry_times(int): Latest number of retries
            agent(str): Agent's name
            model(str): Model name
            result(str): Plan step results
        """

    @abstractmethod
    def remove_by_conv_id(self, conv_id: str) -> None:
        """Remove plan by conversation id.

        Args:
            conv_id(str): conversation id
        """


class GptsMessageMemory(ABC):
    """Gpts message memory interface."""

    @abstractmethod
    def append(self, message: GptsMessage) -> None:
        """Add a message.

        Args:
            message(GptsMessage): Message object
        """

    @abstractmethod
    def update(self, message: GptsMessage) -> None:
        """Update message.

        Args:
            message:

        Returns:

        """

    @abstractmethod
    def get_by_agent(self, conv_id: str, agent: str) -> Optional[List[GptsMessage]]:
        """Return all messages of the agent in the conversation.

        Args:
            conv_id(str): Conversation id
            agent(str): Agent's name

        Returns:
            List[GptsMessage]: List of messages
        """

    @abstractmethod
    def get_between_agents(
        self,
        conv_id: str,
        agent1: str,
        agent2: str,
        current_goal: Optional[str] = None,
    ) -> List[GptsMessage]:
        """Get messages between two agents.

        Query information related to an agent

        Args:
            conv_id(str): Conversation id
            agent1(str): Agent1's name
            agent2(str): Agent2's name
            current_goal(str): Current goal

        Returns:
            List[GptsMessage]: List of messages
        """

    @abstractmethod
    def get_by_conv_id(self, conv_id: str) -> List[GptsMessage]:
        """Return all messages in the conversation.

        Query messages by conv id.

        Args:
            conv_id(str): Conversation id
        Returns:
            List[GptsMessage]: List of messages
        """

    @abstractmethod
    def get_by_message_id(self, message_id: str) -> Optional[GptsMessage]:
        """Return one messages by message id.

        Args:
            message_id:

        Returns:

        """

    @abstractmethod
    def get_last_message(self, conv_id: str) -> Optional[GptsMessage]:
        """Return the last message in the conversation.

        Args:
            conv_id(str): Conversation id

        Returns:
            GptsMessage: The last message in the conversation
        """

    @abstractmethod
    def delete_by_conv_id(self, conv_id: str) -> None:
        """Delete messages by conversation id.

        Args:
            conv_id(str): Conversation id
        """
