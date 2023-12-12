import json
import asyncio
from enum import Enum
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from dataclasses import dataclass, asdict, fields
import dataclasses
from datetime import datetime
import uuid

from dbgpt.agent.common.schema import Status
from dbgpt.agent.agents.agents_mange import AgentsMange
from dbgpt.agent.agents.planner_agent import PlannerAgent
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.agents.planning_group_chat import PlanChat, PlanChatManager
from dbgpt.agent.agents.agent import AgentContext
from dbgpt.agent.memory.gpts_memory import GptsMemory

from .db_gpts_memory import MetaDbGptsPlansMemory, MetaDbGptsMessageMemory

from ..db.gpts_mange_db import GptsInstanceDao, GptsInstanceEntity
from ..db.gpts_conversations_db import GptsConversationsDao, GptsConversationsEntity



class AgentMode(Enum):
    PLAN_EXCUTE = "plan_excute"




# @dataclass
# class DbGpts:
#     gpts_name: str
#     gpts_agents: List[str]
#     gpts_models: List[str]
#     mode: str = AgentMode.PLAN_EXCUTE.value
#
#     language: str = "en"
#     resource_internet: Optional[str] = None
#     resource_db: Optional[str] = None
#     resource_knowledge: Optional[str] = None
#
#
#     @staticmethod
#     def from_dict(d: Dict[str, Any]) -> DbGpts:
#         return DbGpts(
#             gpts_name=d.get("gpts_name"),
#             gpts_agents=d["gpts_agents"],
#             gpts_models=d["gpts_models"],
#             mode=d["mode"],
#             language=d['language'],
#             resource_internet=d["resource_internet"],
#             resource_db=d["resource_db"],
#             resource_knowledge=d["resource_knowledge"],
#         )
#
#     def to_dict(self) -> Dict[str, Any]:
#         return dataclasses.asdict(self)

@dataclass
class DbGptsMessage:
    sender: str
    reciver: str
    content: str
    action_report: str

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> DbGptsMessage:
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



# class DbGpts:
#
#     def __init__(self):
#         self.gpts_intance = GptsInstanceDao()
#         self.gpts_conversations = GptsConversationsDao()
#         self.agent_mange = AgentsMange()
#         self.memory = GptsMemory(plans_memory= MetaDbGptsPlansMemory(), message_memory= MetaDbGptsMessageMemory())
#
#
#     def gpts_create(self, gpts: DbGpts):
#         self.gpts_intance.add(GptsInstanceEntity(**gpts.to_dict()))
#
#
#     def chat_start(self, name:str, user_query: str, user_code:str = None, system_app:str = None):
#         gpts_instance: GptsInstanceEntity = self.gpts_intance.get_by_name(name)
#         agents_name = gpts_instance.gpts_agents.spilt(",")
#         llm_models = gpts_instance.gpts_models.spilt(",")
#         resource_db = json.loads(gpts_instance.resource_db) if gpts_instance.resource_db else None
#         resource_knowledge = json.loads(gpts_instance.resource_knowledge) if gpts_instance.resource_knowledge else None
#         resource_internet = json.loads(gpts_instance.resource_internet) if gpts_instance.resource_internet else None
#
#         ### init chat param
#         conv_id =  uuid.uuid1()
#         context: AgentContext = AgentContext(conv_id=conv_id, gpts_name=gpts_instance.gpts_name)
#         context.resource_db = resource_db
#         context.resource_internet = resource_internet
#         context.resource_knowledge = resource_knowledge
#         context.agents = agents_name
#         context.llm_models = llm_models
#
#         self.gpts_conversations.add(GptsConversationsEntity(
#             conv_id=conv_id,
#             user_goal=user_query,
#             gpts_name= gpts_instance.gpts_name,
#             state=Status.RUNNING.value,
#             max_auto_reply_round= context.max_chat_round,
#             auto_reply_count= 0,
#             user_code=user_code,
#             system_app=system_app
#         ))
#
#         ### default plan excute mode
#         agents = []
#         for name in agents_name:
#             cls = self.agent_mange.get_by_name(name)
#             agents.append(cls( agent_context=context,  memory=common_memory))
#         groupchat = PlanChat(agents=agents, messages=[], max_round=50)
#
#         planner = PlannerAgent(
#             agent_context=context,
#             memory=self.memory,
#             plan_chat=groupchat,
#         )
#         manager = PlanChatManager(plan_chat=groupchat, planner=planner, agent_context=context, memory=common_memory)
#
#         user_proxy = UserProxyAgent(
#             memory=self.memory,
#             agent_context=context
#         )
#
#         ## dbgpts conversation save
#
#         user_proxy.a_initiate_chat(
#             recipient=manager,
#             message=user_query,
#             memory=self.memory,
#         )
#         return conv_id
#
#
#
#
#     async def chat_completions(self, conv_id:str, user_code:str = None, system_app:str = None ):
#         is_complete = False
#         while True:
#             if is_complete:
#                 return
#
#             plans = self.memory.plans_memory.get_by_conv_id(conv_id=conv_id)
#             messages = self.memory.message_memory.get_by_conv_id(conv_id=conv_id)
#
#             task_steps = []
#             for plan in plans:
#                 task_steps.append(DbGptsTaskStep(
#                     task_num=plan.sub_task_num,
#                     task_content=plan.sub_task_content,
#                     state=plan.state,
#                     result=plan.result,
#                     agent_name=plan.sub_task_agent,
#                     model_name=plan.agent_model
#                 ))
#
#             dbgpts_messages = []
#             for message in messages:
#                 dbgpts_messages.append(DbGptsMessage(
#                     sender= message.sender,
#                     reciver= message.reciver,
#                     content= message.content,
#                     action_report=message.action_report
#                 ))
#
#             completion =  DbGptsCompletion(
#                 conv_id=conv_id,
#                 task_steps= task_steps,
#                 messages=dbgpts_messages
#             )
#
#             yield completion
#             await asyncio.sleep(1)
#
#
#     def gpts_conv_list(self, user_code:str = None, system_app:str = None):
#         return self.gpts_conversations.get_convs(user_code, system_app)
