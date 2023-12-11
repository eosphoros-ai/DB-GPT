from enum import Enum
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from dataclasses import dataclass, asdict, fields
import dataclasses
from datetime import datetime
from dbgpt.agent.common.schema import Status

from ..db.gpts_mange_db import GptsInstanceDao, GptsInstanceEntity
from ..db.gpts_conversations_db import GptsConversationsDao, GptsConversationsEntity

class AgentMode(Enum):
    PLAN_EXCUTE = "plan_excute"



@dataclass
class GptsResource:
    type: str
    name: str
    introduction: str

@dataclass
class DbGpts:
    gpts_name: str
    gpts_agents: List[str]
    gpts_models: List[str]
    mode: str = AgentMode.PLAN_EXCUTE.value

    language: str = "en"
    resource_internet: Optional[str] = None
    resource_db: Optional[str] = None
    resource_knowledge: Optional[str] = None


    @staticmethod
    def from_dict(d: Dict[str, Any]) -> DbGpts:
        return DbGpts(
            gpts_name=d.get("gpts_name"),
            gpts_agents=d["gpts_agents"],
            gpts_models=d["gpts_models"],
            mode=d["mode"],
            language=d['language'],
            resource_internet=d["resource_internet"],
            resource_db=d["resource_db"],
            resource_knowledge=d["resource_knowledge"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


@dataclass
class DbGptsCompletion:
    conv_id: str

    task_step: Optional[list[dict]]
    sender: str
    reciver: str
    content: str
    model_name: str
    agent_name: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> DbGptsCompletion:
        return DbGptsCompletion(
            conv_id=d.get("conv_id"),
            task_step=d["task_step"],
            sender=d["sender"],
            reciver=d["reciver"],
            content=d['content'],
            model_name=d["model_name"],
            agent_name=d["agent_name"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)



class DbGpts:

    def __init__(self):
        self.gpts_intance = GptsInstanceDao()
        self.gpts_conversations = GptsConversationsDao()


    def gpts_create(self, gpts: DbGpts):
        self.gpts_intance.add(GptsInstanceEntity(**gpts.to_dict()))


    def chat_start(self, name:str, user_query: str, user_code:str = None, system_app:str = None):
        gpts_instance: GptsInstanceEntity = self.gpts_intance.get_by_name(name)



    def chat_completions(self, conv_id:str, user_code:str = None, system_app:str = None ):



    def gpts_conv_list(self, user_code:str = None, system_app:str = None):


