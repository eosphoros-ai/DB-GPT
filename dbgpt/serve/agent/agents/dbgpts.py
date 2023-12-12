from __future__ import annotations

from enum import Enum
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from dataclasses import dataclass, asdict, fields
import dataclasses




class AgentMode(Enum):
    PLAN_EXCUTE = "plan_excute"


@dataclass
class DbGptsMessage:
    sender: str
    reciver: str
    content: str
    action_report: str

    @staticmethod
    def from_dict(d: Dict[str, Any])->DbGptsMessage:
        return DbGptsMessage(
            sender=d["sender"],
            reciver=d["reciver"],
            content=d['content'],
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
            state=d['state'],
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
