from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from dbgpt.agent.resource.resource_loader import ResourceLoader
from dbgpt.core import LLMClient
from dbgpt.util.annotations import PublicAPI

from ..memory.gpts_memory import GptsMemory


class Agent(ABC):
    async def a_send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        reviewer: Agent,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
    ) -> None:
        """(Abstract async method) Send a message to recipient agent."""

    async def a_receive(
        self,
        message: Optional[Dict],
        sender: Agent,
        reviewer: Agent,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
    ) -> None:
        """(Abstract async method) Receive a message from another agent."""

    async def a_generate_reply(
        self,
        recive_message: Optional[Dict],
        sender: Agent,
        reviewer: Agent = None,
        rely_messages: Optional[List[Dict]] = None,
        **kwargs,
    ) -> Union[str, Dict, None]:
        """(Abstract async method) Generate a reply based on the received messages.

        Args:
            messages (Optional[Dict]): a dict of messages received from other agents.
            sender: sender of an Agent instance.
        Returns:
            str or dict or None: the generated reply. If None, no reply is generated.
        """

    async def a_thinking(
        self, messages: Optional[List[Dict]]
    ) -> Union[str, Dict, None]:
        """Based on the requirements of the current agent, reason about the current task goal through LLM
        Args:
            messages:

        Returns:
            str or dict or None: the generated reply. If None, no reply is generated.
        """

    async def a_review(
        self, message: Union[Dict, str], censored: Agent
    ) -> Tuple[bool, Any]:
        """

        Args:
            message:
            censored:

        Returns:
            bool: whether the message is censored
            Any: the censored message
        """

    async def a_act(
        self,
        message: Optional[str],
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Union[str, Dict, None]:
        """
        Parse the inference results for the current target and execute the inference results using the current agent's executor
        Args:
            messages (list[dict]): a list of messages received.
            sender: sender of an Agent instance.
            **kwargs:
        Returns:
             str or dict or None: the agent action reply. If None, no reply is generated.
        """

    async def a_verify(
        self,
        message: Optional[Dict],
        sender: Agent,
        reviewer: Agent,
        **kwargs,
    ) -> Union[str, Dict, None]:
        """
        Verify whether the current execution results meet the target expectations
        Args:
            messages:
            sender:
            **kwargs:

        Returns:

        """


@dataclasses.dataclass
class AgentContext:
    conv_id: str
    gpts_app_name: str = None
    language: str = None
    max_chat_round: Optional[int] = 100
    max_retry_round: Optional[int] = 10
    max_new_tokens: Optional[int] = 1024
    temperature: Optional[float] = 0.5
    allow_format_str_template: Optional[bool] = False

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
@PublicAPI(stability="beta")
class AgentGenerateContext:
    """A class to represent the input of a Agent."""

    message: Optional[Dict]
    sender: Agent
    reviewer: Agent
    silent: Optional[bool] = False

    rely_messages: List[Dict] = dataclasses.field(default_factory=list)
    final: Optional[bool] = True

    memory: Optional[GptsMemory] = None
    agent_context: Optional[AgentContext] = None
    resource_loader: Optional[ResourceLoader] = None
    llm_client: Optional[LLMClient] = None

    round_index: int = None

    def to_dict(self) -> Dict:
        return dataclasses.asdict(self)
