from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from dbgpt.agent.agents.agent import AgentResource


class AgentMode(Enum):
    PLAN_EXCUTE = "plan_excute"


@dataclass
class DbGptsInstance:
    gpts_name: str
    gpts_describe: str
    gpts_agents: list[str]
    resource_db: Optional[AgentResource] = None
    resource_internet: Optional[AgentResource] = None
    resource_knowledge: Optional[AgentResource] = None
    gpts_models: Optional[Dict[str, List[str]]] = None
    language: str = "en"
    user_code: str = None
    sys_code: str = None

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class DbGptsMessage:
    sender: str
    receiver: str
    content: str
    action_report: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> DbGptsMessage:
        return DbGptsMessage(
            sender=d["sender"],
            receiver=d["receiver"],
            content=d["content"],
            model_name=d["model_name"],
            agent_name=d["agent_name"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class DbGptsTaskStep:
    task_num: str
    task_content: str
    state: str
    result: str
    agent_name: str
    model_name: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> DbGptsTaskStep:
        return DbGptsTaskStep(
            task_num=d["task_num"],
            task_content=d["task_content"],
            state=d["state"],
            result=d["result"],
            agent_name=d["agent_name"],
            model_name=d["model_name"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class DbGptsCompletion:
    conv_id: str
    task_steps: Optional[List[DbGptsTaskStep]]
    messages: Optional[List[DbGptsMessage]]

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> DbGptsCompletion:
        return DbGptsCompletion(
            conv_id=d.get("conv_id"),
            task_steps=DbGptsTaskStep.from_dict(d["task_steps"]),
            messages=DbGptsMessage.from_dict(d["messages"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)
