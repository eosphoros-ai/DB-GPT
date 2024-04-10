"""Agent Interface."""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

from dbgpt.core import LLMClient
from dbgpt.util.annotations import PublicAPI

from ..actions.action import ActionOutput
from ..memory.gpts_memory import GptsMemory
from ..resource.resource_loader import ResourceLoader


class Agent(ABC):
    """Agent Interface."""

    @abstractmethod
    async def send(
        self,
        message: AgentMessage,
        recipient: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
    ) -> None:
        """Send a message to recipient agent.

        Args:
            message(AgentMessage): the message to be sent.
            recipient(Agent): the recipient agent.
            reviewer(Agent): the reviewer agent.
            request_reply(bool): whether to request a reply.
            is_recovery(bool): whether the message is a recovery message.

        Returns:
            None
        """

    @abstractmethod
    async def receive(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
    ) -> None:
        """Receive a message from another agent.

        Args:
            message(AgentMessage): the received message.
            sender(Agent): the sender agent.
            reviewer(Agent): the reviewer agent.
            request_reply(bool): whether to request a reply.
            silent(bool): whether to be silent.
            is_recovery(bool): whether the message is a recovery message.

        Returns:
            None
        """

    @abstractmethod
    async def generate_reply(
        self,
        received_message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> AgentMessage:
        """Generate a reply based on the received messages.

        Args:
            received_message(AgentMessage): the received message.
            sender: sender of an Agent instance.
            reviewer: reviewer of an Agent instance.
            rely_messages: a list of messages received.

        Returns:
            AgentMessage: the generated reply. If None, no reply is generated.
        """

    @abstractmethod
    async def thinking(
        self, messages: List[AgentMessage], prompt: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Think and reason about the current task goal.

        Based on the requirements of the current agent, reason about the current task
        goal through LLM

        Args:
            messages(List[AgentMessage]): the messages to be reasoned
            prompt(str): the prompt to be reasoned

        Returns:
            Tuple[Union[str, Dict, None], Optional[str]]: First element is the generated
                reply. If None, no reply is generated. The second element is the model
                name of current task.
        """

    @abstractmethod
    async def review(self, message: Optional[str], censored: Agent) -> Tuple[bool, Any]:
        """Review the message based on the censored message.

        Args:
            message:
            censored:

        Returns:
            bool: whether the message is censored
            Any: the censored message
        """

    @abstractmethod
    async def act(
        self,
        message: Optional[str],
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Optional[ActionOutput]:
        """Act based on the LLM inference results.

        Parse the inference results for the current target and execute the inference
        results using the current agent's executor

        Args:
            message: the message to be executed
            sender: sender of an Agent instance.
            reviewer: reviewer of an Agent instance.
            **kwargs:

        Returns:
             ActionOutput: the action output of the agent.
        """

    @abstractmethod
    async def verify(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Tuple[bool, Optional[str]]:
        """Verify whether the current execution results meet the target expectations.

        Args:
            message: the message to be verified
            sender: sender of an Agent instance.
            reviewer: reviewer of an Agent instance.
            **kwargs:

        Returns:
            Tuple[bool, Optional[str]]: whether the verification is successful and the
                verification result.
        """

    @abstractmethod
    def get_name(self) -> str:
        """Return name of the agent."""

    @abstractmethod
    def get_profile(self) -> str:
        """Return profile of the agent."""

    @abstractmethod
    def get_describe(self) -> str:
        """Return describe of the agent."""


@dataclasses.dataclass
class AgentContext:
    """A class to represent the context of an Agent."""

    conv_id: str
    gpts_app_name: Optional[str] = None
    language: Optional[str] = None
    max_chat_round: int = 100
    max_retry_round: int = 10
    max_new_tokens: int = 1024
    temperature: float = 0.5
    allow_format_str_template: Optional[bool] = False

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the AgentContext."""
        return dataclasses.asdict(self)


@dataclasses.dataclass
@PublicAPI(stability="beta")
class AgentGenerateContext:
    """A class to represent the input of a Agent."""

    message: Optional[AgentMessage]
    sender: Optional[Agent] = None
    reviewer: Optional[Agent] = None
    silent: Optional[bool] = False

    rely_messages: List[AgentMessage] = dataclasses.field(default_factory=list)
    final: Optional[bool] = True

    memory: Optional[GptsMemory] = None
    agent_context: Optional[AgentContext] = None
    resource_loader: Optional[ResourceLoader] = None
    llm_client: Optional[LLMClient] = None

    round_index: Optional[int] = None

    def to_dict(self) -> Dict:
        """Return a dictionary representation of the AgentGenerateContext."""
        return dataclasses.asdict(self)


ActionReportType = Dict[str, Any]
MessageContextType = Union[str, Dict[str, Any]]


@dataclasses.dataclass
@PublicAPI(stability="beta")
class AgentReviewInfo:
    """Message object for agent communication."""

    approve: bool = False
    comments: Optional[str] = None

    def copy(self) -> "AgentReviewInfo":
        """Return a copy of the current AgentReviewInfo."""
        return AgentReviewInfo(approve=self.approve, comments=self.comments)


@dataclasses.dataclass
@PublicAPI(stability="beta")
class AgentMessage:
    """Message object for agent communication."""

    content: Optional[str] = None
    name: Optional[str] = None
    context: Optional[MessageContextType] = None
    action_report: Optional[ActionReportType] = None
    review_info: Optional[AgentReviewInfo] = None
    current_goal: Optional[str] = None
    model_name: Optional[str] = None
    role: Optional[str] = None
    success: Optional[bool] = None

    def to_dict(self) -> Dict:
        """Return a dictionary representation of the AgentMessage."""
        return dataclasses.asdict(self)

    def to_llm_message(self) -> Dict[str, Any]:
        """Return a dictionary representation of the AgentMessage."""
        return {
            "content": self.content,
            "context": self.context,
            "role": self.role,
        }

    @classmethod
    def from_llm_message(cls, message: Dict[str, Any]) -> AgentMessage:
        """Create an AgentMessage object from a dictionary."""
        return cls(
            content=message.get("content"),
            context=message.get("context"),
            role=message.get("role"),
        )

    @classmethod
    def from_messages(cls, messages: List[Dict[str, Any]]) -> List[AgentMessage]:
        """Create a list of AgentMessage objects from a list of dictionaries."""
        results = []
        field_names = [f.name for f in dataclasses.fields(cls)]
        for message in messages:
            kwargs = {
                key: value for key, value in message.items() if key in field_names
            }
            results.append(cls(**kwargs))
        return results

    def copy(self) -> "AgentMessage":
        """Return a copy of the current AgentMessage."""
        copied_context: Optional[MessageContextType] = None
        if self.context:
            if isinstance(self.context, dict):
                copied_context = self.context.copy()
            else:
                copied_context = self.context
        copied_action_report = self.action_report.copy() if self.action_report else None
        copied_review_info = self.review_info.copy() if self.review_info else None
        return AgentMessage(
            content=self.content,
            name=self.name,
            context=copied_context,
            action_report=copied_action_report,
            review_info=copied_review_info,
            current_goal=self.current_goal,
            model_name=self.model_name,
            role=self.role,
            success=self.success,
        )
