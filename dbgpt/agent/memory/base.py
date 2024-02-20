from __future__ import annotations

import dataclasses
from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from dbgpt.agent.common.schema import Status


@dataclass
class GptsPlan:
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

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> GptsPlan:
        return GptsPlan(
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


@dataclass
class GptsMessage:
    """Gpts plan"""

    conv_id: str
    sender: str

    receiver: str
    role: str
    content: str
    rounds: Optional[int]
    current_goal: str = None
    context: Optional[str] = None
    review_info: Optional[str] = None
    action_report: Optional[str] = None
    model_name: Optional[str] = None
    created_at: datetime = datetime.utcnow
    updated_at: datetime = datetime.utcnow

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> GptsMessage:
        return GptsMessage(
            conv_id=d["conv_id"],
            sender=d["sender"],
            receiver=d["receiver"],
            role=d["role"],
            content=d["content"],
            rounds=d["rounds"],
            model_name=d["model_name"],
            current_goal=d["current_goal"],
            context=d["context"],
            review_info=d["review_info"],
            action_report=d["action_report"],
            created_at=d["created_at"],
            updated_at=d["updated_at"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class GptsPlansMemory(ABC):
    def batch_save(self, plans: list[GptsPlan]):
        """
        batch save gpts plan
        Args:
            plans: panner generate plans info
        Returns:
            None
        """
        pass

    def get_by_conv_id(self, conv_id: str) -> List[GptsPlan]:
        """
        get plans by conv_id
        Args:
            conv_id: conversation id
        Returns:
            List of planning steps
        """

    def get_by_conv_id_and_num(
        self, conv_id: str, task_nums: List[int]
    ) -> List[GptsPlan]:
        """
        get
        Args:
            conv_id: conversation id
            task_nums: List of sequence numbers of plans in the same conversation

        Returns:
            List of planning steps

        """

    def get_todo_plans(self, conv_id: str) -> List[GptsPlan]:
        """
        Get unfinished planning steps
        Args:
            conv_id: conversation id

        Returns:
            List of planning steps
        """

    def complete_task(self, conv_id: str, task_num: int, result: str):
        """
        Complete designated planning step
        Args:
            conv_id: conversation id
            task_num: Planning step num
            result: Plan step results

        Returns:
            None
        """

    def update_task(
        self,
        conv_id: str,
        task_num: int,
        state: str,
        retry_times: int,
        agent: str = None,
        model: str = None,
        result: str = None,
    ):
        """
        Update planning step information
        Args:
            conv_id: conversation id
            task_num: Planning step num
            state: the status to update to
            retry_times: Latest number of retries
            agent: Agent's name

        Returns:

        """

    def remove_by_conv_id(self, conv_id: str):
        """
        Delete planning
        Args:
            conv_id:

        Returns:

        """


class GptsMessageMemory(ABC):
    def append(self, message: GptsMessage):
        """
        Add a message
        Args:
            message:

        Returns:

        """

    def get_by_agent(self, conv_id: str, agent: str) -> Optional[List[GptsMessage]]:
        """
        Query information related to an agent
        Args:
            agent:agent's name

        Returns:
            messages
        """

    def get_between_agents(
        self,
        conv_id: str,
        agent1: str,
        agent2: str,
        current_goal: Optional[str] = None,
    ) -> Optional[List[GptsMessage]]:
        """
        Query information related to an agent
        Args:
            agent:agent's name

        Returns:
            messages
        """

    def get_by_conv_id(self, conv_id: str) -> Optional[List[GptsMessage]]:
        """
        Query messages by conv id
        Args:
            conv_id:

        Returns:

        """

    def get_last_message(self, conv_id: str) -> Optional[GptsMessage]:
        """
        Query last message
        Args:
            conv_id:

        Returns:

        """
