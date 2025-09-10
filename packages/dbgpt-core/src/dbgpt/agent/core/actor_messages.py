from dataclasses import dataclass
from typing import Dict, List, Optional

from .action.base import ActionOutput
from .agent import ActorProxyAgent, AgentMessage, AgentMessageRequest


@dataclass
class AgentLoopInitMessage:
    request: AgentMessageRequest
    sender: ActorProxyAgent
    reply_message: AgentMessage
    thinking_messages: List[AgentMessage]
    received_message: AgentMessage
    current_retry_counter: int = 0
    observation: Optional[str] = None
    reviewer: Optional[ActorProxyAgent] = None
    resource_references: Optional[Dict] = None
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    historical_dialogues: Optional[List[AgentMessage]] = (None,)


@dataclass
class ThinkingRequest:
    init_message: AgentLoopInitMessage
    current_goal: Optional[str] = None


@dataclass
class ThinkingResponse:
    init_message: AgentLoopInitMessage
    model_name: str
    text: str
    thinking_text: Optional[str] = None


@dataclass
class ReviewRequest:
    thinking_response: ThinkingResponse


@dataclass
class ReviewResponse:
    thinking_response: ThinkingResponse
    approved: bool
    comments: Optional[str] = None


@dataclass
class ActionRequest:
    thinking_response: ThinkingResponse


@dataclass
class ActionResponse:
    thinking_response: ThinkingResponse
    action_report: Optional[ActionOutput] = None


@dataclass
class ActionVerifyRequest:
    action_response: ActionResponse


@dataclass
class ActionVerifyResponse:
    action_response: ActionResponse
    verified: bool
    comments: Optional[str] = None
