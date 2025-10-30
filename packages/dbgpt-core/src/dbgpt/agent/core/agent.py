"""Agent Interface."""

from __future__ import annotations

import dataclasses
import json
import logging
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import lyricore as lc

from dbgpt.core import LLMClient
from dbgpt.util.annotations import PublicAPI

from ...util.json_utils import serialize
from .action.base import ActionOutput
from .memory.agent_memory import AgentMemory
from .memory.gpts import GptsMessage

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """Agent State Enum."""

    IDLE = "IDLE"
    THINKING = "THINKING"
    ACTING = "ACTING"
    TASK_SUCCEEDED = "TASK_SUCCEEDED"
    TASK_FAILED = "TASK_FAILED"


@dataclasses.dataclass
class AgentStateMessage:
    name: str
    role: str
    state: AgentState


@dataclasses.dataclass
class AgentStateIdleMessage(AgentStateMessage):
    state: AgentState = AgentState.IDLE


@dataclasses.dataclass
class AgentStateThinking(AgentStateMessage):
    state: AgentState = AgentState.THINKING
    current_retry_counter: int = 0
    conv_id: Optional[str] = None


@dataclasses.dataclass
class AgentStateActing(AgentStateMessage):
    state: AgentState = AgentState.ACTING
    current_retry_counter: int = 0
    conv_id: Optional[str] = None


@dataclasses.dataclass
class AgentStateTaskResult(AgentStateMessage):
    state: Union[AgentState.TASK_SUCCEEDED, AgentState.TASK_FAILED]
    result: Optional[str] = None
    action_report: Optional[ActionOutput] = None
    conv_id: Optional[str] = None
    rounds: Optional[int] = 0
    current_retry_counter: int = 0

    @property
    def is_success(self) -> bool:
        return self.state == AgentState.TASK_SUCCEEDED


@dataclasses.dataclass
class AgentMessageRequest:
    message: AgentMessage
    sender: ActorProxyAgent
    reviewer: Optional[ActorProxyAgent] = None
    request_reply: Optional[bool] = True
    is_recovery: Optional[bool] = False
    silent: Optional[bool] = False
    is_retry_chat: bool = False
    last_speaker_name: Optional[str] = None
    rely_messages: Optional[List[AgentMessage]] = None
    historical_dialogues: Optional[List[AgentMessage]] = None
    current_retry_counter: int = 0


class ActorProxyAgent:
    """Agent Proxy for interacting with agents via ActorRef.

    It can be serialized and passed around between distributed machines.
    """

    def __init__(
        self,
        agent_context: AgentContext,
        actor_ref: lc.ActorRef,
        name: str,
        role: str,
        desc: Optional[str] = None,
        avatar: Optional[str] = None,
    ):
        self.agent_context = agent_context
        self.actor_ref = actor_ref
        self._name = name
        self._role = role
        self._desc = desc
        self._avatar = avatar

    async def tell(
        self,
        message: AgentMessage,
        reviewer: Optional["ActorProxyAgent"] = None,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
        silent: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        sender: Optional["ActorProxyAgent"] = None,
        sender_agent: Optional[ActorProxyAgent] = None,
        current_retry_counter=0,
    ) -> None:
        actor_ctx = lc.get_current_message_context()
        sender_ref = actor_ctx.self_ref
        sender_agent = sender_agent or sender
        sender = sender or ActorProxyAgent(
            agent_context=self.agent_context,
            actor_ref=sender_ref,
            name=sender_agent.name if sender_agent else "unknown",
            role=sender_agent.role if sender_agent else "unknown",
            desc=sender_agent.desc if sender_agent else None,
            avatar=sender_agent.avatar if sender_agent else None,
        )

        req = AgentMessageRequest(
            message=message,
            sender=sender,
            reviewer=reviewer,
            request_reply=request_reply,
            is_recovery=is_recovery,
            silent=silent,
            is_retry_chat=is_retry_chat,
            last_speaker_name=last_speaker_name,
            rely_messages=rely_messages,
            historical_dialogues=historical_dialogues,
            current_retry_counter=current_retry_counter,
        )
        return await self.actor_ref.tell(req)

    async def tell_request(
        self,
        req: "AgentMessageRequest",
    ) -> None:
        return await self.actor_ref.tell(req)

    async def ask(
        self,
        message: AgentMessage,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
        silent: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
    ) -> Any:
        actor_ctx = lc.get_current_message_context()
        sender_ref = actor_ctx.self_ref
        req = AgentMessageRequest(
            message=message,
            sender=sender_ref,
            reviewer=reviewer,
            request_reply=request_reply,
            is_recovery=is_recovery,
            silent=silent,
            is_retry_chat=is_retry_chat,
            last_speaker_name=last_speaker_name,
            rely_messages=rely_messages,
            historical_dialogues=historical_dialogues,
        )
        res = await self.actor_ref.ask(req)
        return res

    @property
    def name(self) -> str:
        return self._name

    @property
    def role(self) -> str:
        return self._role

    @property
    def desc(self) -> Optional[str]:
        return self._desc

    @property
    def avatar(self) -> str:
        return self._avatar

    @property
    def not_null_agent_context(self) -> AgentContext:
        """Get the agent context.

        Returns:
            AgentContext: The agent context.

        Raises:
            ValueError: If the agent context is not initialized.
        """
        if not self.agent_context:
            raise ValueError("Agent context is not initialized！")
        return self.agent_context

    async def agent_full_desc(self):
        return await self.actor_ref.agent_full_desc.ask()

    async def subscribe(
        self, ref: Union["ActorProxyAgent", lc.ActorRef], topic: Optional[str] = None
    ):
        if isinstance(ref, ActorProxyAgent):
            ref = ref.actor_ref
        try:
            await self.actor_ref.subscribe.tell(ref, topic)
        except Exception as e:
            logger.error(f"Failed to subscribe to {ref}: {e}")
            raise e


class Agent(ABC):
    """Agent Interface."""

    @abstractmethod
    async def generate_reply(self, request: AgentMessageRequest):
        """Generate a reply based on the received messages.

        Args:
            request(AgentMessageRequest): the request containing the received message
                and other information.
        """

    @abstractmethod
    async def thinking(
        self,
        messages: List[AgentMessage],
        reply_message_id: str,
        reply_message: AgentMessage,
        sender: Optional[ActorProxyAgent] = None,
        prompt: Optional[str] = None,
        current_goal: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
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
    async def review(
        self, message: Optional[str], censored: ActorProxyAgent
    ) -> Tuple[bool, Any]:
        """Review the message based on the censored message.

        Args:
            message: the message to be reviewed
            censored: The censored agent.

        Returns:
            bool: whether the message is censored
            Any: the censored message
        """

    @abstractmethod
    async def act(
        self,
        message: AgentMessage,
        sender: ActorProxyAgent,
        reviewer: Optional[ActorProxyAgent] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        """Act based on the LLM inference results.

        Parse the inference results for the current target and execute the inference
        results using the current agent's executor

        Args:
            message: the message to be executed
            sender: sender of an Agent instance.
            reviewer: reviewer of an Agent instance.
            is_retry_chat: whether the current chat is a retry chat.
            last_speaker_name: the name of the last speaker.
            **kwargs:

        Returns:
             ActionOutput: the action output of the agent.
        """

    @abstractmethod
    async def verify(
        self,
        message: AgentMessage,
        sender: ActorProxyAgent,
        reviewer: Optional[ActorProxyAgent] = None,
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

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the agent."""

    @property
    @abstractmethod
    def avatar(self) -> str:
        """Return the avatar of the agent."""

    @property
    @abstractmethod
    def role(self) -> str:
        """Return the role of the agent."""

    @property
    @abstractmethod
    def desc(self) -> Optional[str]:
        """Return the description of the agent."""


@dataclasses.dataclass
class AgentContext:
    """A class to represent the context of an Agent."""

    conv_id: str
    conv_session_id: str
    trace_id: Optional[str] = None
    rpc_id: Optional[str] = None
    gpts_app_code: Optional[str] = None
    gpts_app_name: Optional[str] = None
    language: Optional[str] = None
    max_chat_round: int = 100
    max_retry_round: int = 10
    max_new_tokens: int = 8 * 1024
    temperature: float = 0.5
    allow_format_str_template: Optional[bool] = False
    verbose: bool = False

    app_link_start: bool = False
    enable_vis_message: bool = True
    incremental: bool = True
    stream: bool = True

    output_process_message: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Return a dictionary representation of the AgentContext."""
        return dataclasses.asdict(self)


@dataclasses.dataclass
@PublicAPI(stability="beta")
class AgentGenerateContext:
    """A class to represent the input of a Agent."""

    message: Optional[AgentMessage]
    sender: ActorProxyAgent
    reviewer: Optional[Agent] = None
    silent: Optional[bool] = False

    already_failed: bool = False
    last_speaker: Optional[ActorProxyAgent] = None

    already_started: bool = False
    begin_agent: Optional[str] = None

    rely_messages: List[AgentMessage] = dataclasses.field(default_factory=list)
    final: Optional[bool] = True

    memory: Optional[AgentMemory] = None
    agent_context: Optional[AgentContext] = None
    llm_client: Optional[LLMClient] = None

    round_index: Optional[int] = None

    def to_dict(self) -> Dict:
        """Return a dictionary representation of the AgentGenerateContext."""
        return dataclasses.asdict(self)


ActionReportType = ActionOutput
MessageContextType = Union[str, Dict[str, Any]]
ResourceReferType = Dict[str, Any]


@dataclasses.dataclass
@PublicAPI(stability="beta")
class AgentReviewInfo:
    """Message object for agent communication."""

    approve: bool = False
    comments: Optional[str] = None

    def copy(self) -> "AgentReviewInfo":
        """Return a copy of the current AgentReviewInfo."""
        return AgentReviewInfo(approve=self.approve, comments=self.comments)

    def to_dict(self) -> Dict:
        """Return a dictionary representation of the AgentMessage."""
        return dataclasses.asdict(self)


@dataclasses.dataclass
@PublicAPI(stability="beta")
class AgentMessage:
    """Message object for agent communication."""

    message_id: Optional[str] = None
    content: Optional[str] = None
    thinking: Optional[str] = None
    name: Optional[str] = None
    rounds: int = 0
    round_id: Optional[str] = None
    context: Optional[MessageContextType] = None
    action_report: Optional[ActionReportType] = None
    review_info: Optional[AgentReviewInfo] = None
    current_goal: Optional[str] = None
    goal_id: Optional[str] = None
    model_name: Optional[str] = None
    role: Optional[str] = None
    success: bool = True
    resource_info: Optional[ResourceReferType] = None
    show_message: bool = True
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None

    def to_dict(self) -> Dict:
        """Return a dictionary representation of the AgentMessage."""
        result = dataclasses.asdict(self)

        if self.action_report:
            result["action_report"] = (
                self.action_report.to_dict()
            )  # 将 action_report 转换为字典
        return result

    def to_llm_message(self) -> Dict[str, Any]:
        """Return a dictionary representation of the AgentMessage."""
        content = self.content
        action_report = self.action_report
        if action_report:
            content = action_report.content
        return {
            "content": content,  # use tool data as message
            "context": self.context,
            "role": self.role,
        }

    @classmethod
    def init_new(
        cls,
        content: Optional[str] = None,
        current_goal: Optional[str] = None,
        goal_id: Optional[str] = None,
        context: Optional[dict] = None,
        rounds: Optional[int] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        show_message: bool = True,
    ):
        return cls(
            message_id=uuid.uuid4().hex,
            content=content,
            current_goal=current_goal,
            goal_id=goal_id,
            context=context,
            rounds=rounds,
            round_id=uuid.uuid4().hex,
            name=name,
            role=role,
            show_message=show_message,
        )

    @classmethod
    def from_llm_message(cls, message: Dict[str, Any]) -> AgentMessage:
        """Create an AgentMessage object from a dictionary."""
        return cls(
            message_id=uuid.uuid4().hex,
            content=message.get("content"),
            context=message.get("context"),
            role=message.get("role"),
            rounds=message.get("rounds", 0),
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
            kwargs["message_id"] = uuid.uuid4().hex
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

        copied_review_info = self.review_info.copy() if self.review_info else None
        return AgentMessage(
            content=self.content,
            thinking=self.thinking,
            name=self.name,
            context=copied_context,
            rounds=self.rounds,
            action_report=self.action_report,
            review_info=copied_review_info,
            current_goal=self.current_goal,
            goal_id=self.goal_id,
            model_name=self.model_name,
            role=self.role,
            success=self.success,
            resource_info=self.resource_info,
            system_prompt=self.system_prompt,
            user_prompt=self.user_prompt,
        )

    def get_dict_context(self) -> Dict[str, Any]:
        """Return the context as a dictionary."""
        if isinstance(self.context, dict):
            return self.context
        return {}

    def to_gpts_message(
        self,
        sender: "ConversableAgent",
        receiver: Optional["ConversableAgent"] = None,
        role: Optional[str] = None,
        receiver_role: Optional[str] = None,
        receiver_name: Optional[str] = None,
    ) -> GptsMessage:
        gpts_message: GptsMessage = GptsMessage(
            conv_id=sender.not_null_agent_context.conv_id,
            conv_session_id=sender.not_null_agent_context.conv_session_id,
            message_id=self.message_id if self.message_id else uuid.uuid4().hex,
            sender=sender.role,
            sender_name=sender.name,
            # receiver=receiver.role if receiver else sender.role,
            # receiver_name=receiver.name if receiver else sender.name,
            receiver=receiver_role if receiver_role else self.role,
            receiver_name=receiver_name if receiver_name else self.name,
            role=role,
            avatar=sender.avatar,
            rounds=self.rounds,
            is_success=self.success,
            app_code=sender.not_null_agent_context.gpts_app_code,
            app_name=sender.not_null_agent_context.gpts_app_name,
            current_goal=self.current_goal,
            goal_id=self.goal_id,
            content=self.content if self.content else "",
            thinking=self.thinking if self.thinking else "",
            context=(
                json.dumps(self.context, default=serialize, ensure_ascii=False)
                if self.context
                else None
            ),
            review_info=(
                json.dumps(self.review_info.to_dict(), ensure_ascii=False)
                if self.review_info
                else None
            ),
            action_report=(
                json.dumps(self.action_report.to_dict(), ensure_ascii=False)
                if self.action_report
                else None
            ),
            model_name=self.model_name,
            resource_info=(
                json.dumps(self.resource_info) if self.resource_info else None
            ),
            user_prompt=self.user_prompt,
            system_prompt=self.system_prompt,
            show_message=self.show_message,
        )
        return gpts_message
