import logging
import json
import asyncio
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from fastapi import (
    APIRouter,
    Body,
    UploadFile,
    File,
)
from fastapi.responses import StreamingResponse

from abc import ABC
from typing import List

from dbgpt.app.openapi.api_view_model import (
    Result,
    ConversationVo
)
from dbgpt.util.json_utils import EnhancedJSONEncoder
from dbgpt.serve.agent.model import (
    PluginHubParam,
    PagenationFilter,
    PagenationResult,
    PluginHubFilter,
)

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

from .dbgpts import DbGptsCompletion, DbGptsTaskStep, DbGptsMessage, DbGptsInstance
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.agent.agents.agents_mange import agent_mange
from dbgpt._private.config import Config
from dbgpt.model.cluster.controller.controller import BaseModelController
from dbgpt.agent.memory.gpts_memory import GptsMessage

CFG = Config()

import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)


class MultiAgents(BaseComponent, ABC):
    name = ComponentType.MULTI_AGENTS

    def init_app(self, system_app: SystemApp):
        system_app.app.include_router(router, prefix="/api", tags=["Multi-Agents"])

    def __init__(self):
        self.gpts_intance = GptsInstanceDao()
        self.gpts_conversations = GptsConversationsDao()
        self.memory = GptsMemory(plans_memory=MetaDbGptsPlansMemory(), message_memory=MetaDbGptsMessageMemory())

    def gpts_create(self, entity: GptsInstanceEntity):
        self.gpts_intance.add(entity)

    def _get_model_priority(self, name, llm_models_priority):
        model_priority = None
        if name in llm_models_priority:
            model_priority = llm_models_priority[name]
        else:
            model_priority = llm_models_priority['default']
        return model_priority

    async def plan_chat(self, name: str, user_query: str, conv_id: str, user_code: str = None, sys_code: str = None):
        gpts_instance: GptsInstanceEntity = self.gpts_intance.get_by_name(name)
        if gpts_instance is None:
            raise ValueError(f"can't find dbgpts!{name}")
        agents_names = json.loads(gpts_instance.gpts_agents)
        llm_models_priority = json.loads(gpts_instance.gpts_models)
        resource_db = json.loads(gpts_instance.resource_db) if gpts_instance.resource_db else None
        resource_knowledge = json.loads(gpts_instance.resource_knowledge) if gpts_instance.resource_knowledge else None
        resource_internet = json.loads(gpts_instance.resource_internet) if gpts_instance.resource_internet else None

        ### init chat param
        context: AgentContext = AgentContext(conv_id=conv_id, gpts_name=gpts_instance.gpts_name)
        context.resource_db = resource_db
        context.resource_internet = resource_internet
        context.resource_knowledge = resource_knowledge
        context.agents = agents_names

        model_controller = CFG.SYSTEM_APP.get_component(
            ComponentType.MODEL_CONTROLLER, BaseModelController
        )
        types = set()
        models = await model_controller.get_all_instances(healthy_only=True)
        for model in models:
            worker_name, worker_type = model.model_name.split("@")
            if worker_type == "llm":
                types.add(worker_name)

        context.llm_models = list(types)

        agent_map = defaultdict()

        ### default plan excute mode
        agents = []
        for name in agents_names:
            cls = agent_mange.get_by_name(name)
            model_priority=self._get_model_priority(name, llm_models_priority)

            agent = cls(agent_context=context, memory=self.memory, model_priority=model_priority)
            agents.append(agent)
            agent_map[name] = agent

        groupchat = PlanChat(agents=agents, messages=[], max_round=50)
        planner = PlannerAgent(
            agent_context=context,
            memory=self.memory,
            plan_chat=groupchat,
            model_priority=self._get_model_priority(PlannerAgent.NAME, llm_models_priority)
        )
        agent_map[planner.name] = planner

        manager = PlanChatManager(plan_chat=groupchat, model_priority=self._get_model_priority(PlanChatManager.NAME, llm_models_priority), planner=planner, agent_context=context, memory=self.memory)
        agent_map[manager.name] = manager

        user_proxy = UserProxyAgent(
            memory=self.memory,
            agent_context=context
        )
        agent_map[user_proxy.name] = user_proxy

        gpts_conversation = self.gpts_conversations.get_by_conv_id(conv_id)
        if gpts_conversation is None:
            self.gpts_conversations.add(GptsConversationsEntity(
                conv_id=conv_id,
                user_goal=user_query,
                gpts_name=gpts_instance.gpts_name,
                state=Status.RUNNING.value,
                max_auto_reply_round=context.max_chat_round,
                auto_reply_count=0,
                user_code=user_code,
                sys_code=sys_code
            ))

            ## dbgpts conversation save
            try:

                await user_proxy.a_initiate_chat(
                    recipient=manager,
                    message=user_query,
                    memory=self.memory,
                )
            except Exception as e:
                logger.error(f"chat abnormal termination！{str(e)}", e)
                self.gpts_conversations.update(conv_id, Status.FAILED.value)

        else:
            # retry chat
            self.gpts_conversations.update(conv_id, Status.RUNNING.value)
            try:
                await  user_proxy.a_retry_chat(
                    recipient=manager,
                    agent_map=agent_map,
                    memory=self.memory,

                )
            except Exception as e:
                logger.error(f"chat abnormal termination！{str(e)}", e)
                self.gpts_conversations.update(conv_id, Status.FAILED.value)

        self.gpts_conversations.update(conv_id, Status.COMPLETE.value)
        return conv_id

    @staticmethod
    def _messages_to_agents_vis(messages: List[GptsMessage]):
        if messages is None or len(messages) <=0:
            return ""
        messages_view = []
        for message in messages:
            messages_view.append({
                "sender": message.sender,
                "receiver": message.receiver,
                "model": message.model_name,
                "markdown": message.content  # TODO view message
            })
        messages_content = json.dumps(messages_view)
        return f"```agent-messages\n{messages_content}\n```"

    @staticmethod
    def _messages_to_plan_vis(messages: List[Dict]):
        if messages is None or len(messages) <=0:
            return ""
        messages_content = json.dumps(messages)
        return f"```agent-plans\n{messages_content}\n```"


    async def _one_plan_chat_competions(self,  conv_id: str, user_code: str = None, system_app: str = None):
        plans = self.memory.plans_memory.get_by_conv_id(conv_id=conv_id)
        messages = self.memory.message_memory.get_by_conv_id(conv_id=conv_id)

        messages_group = defaultdict(list)
        for item in messages:
            messages_group[item.current_gogal].append(item)

        plans_info_map = defaultdict()
        for plan in plans:
            plans_info_map[plan.sub_task_content] = {
                "name": plan.sub_task_title,
                "num": plan.sub_task_num,
                "status": plan.state,
                "agent": plan.sub_task_agent,
                "markdown": self._messages_to_agents_vis(messages_group.get(plan.sub_task_content))
            }

        normal_messages = []
        if messages_group:
            for key, value in messages_group.items():
                if key not in plans_info_map:
                    normal_messages.extend(value)
        return f"{self._messages_to_agents_vis(normal_messages)}\n{self._messages_to_plan_vis(list(plans_info_map.values()))}"


    async def chat_completions(self, conv_id: str, user_code: str = None, system_app: str = None):
        is_complete = False
        while True:
            if is_complete:
                return
            gpts_conv = self.gpts_conversations.get_by_conv_id(conv_id)
            if  gpts_conv:
                is_complete = True if gpts_conv.state in [Status.COMPLETE.value, Status.FAILED.value] else False

            yield await self._one_plan_chat_competions(conv_id, user_code, system_app)
            await asyncio.sleep(10)

    def gpts_conv_list(self, user_code: str = None, system_app: str = None):
        return self.gpts_conversations.get_convs(user_code, system_app)


multi_agents = MultiAgents()

@router.post("/v1/dbbgpts/agents/list", response_model=Result[str])
async def agents_list():
    logger.info("agents_list!")
    try:
        agents = agent_mange.all_agents()
        return Result.succ(agents)
    except Exception as e:
        return Result.failed(code="E30001", msg=str(e))

@router.post("/v1/dbbgpts/create", response_model=Result[str])
async def create_dbgpts(gpts_instance: DbGptsInstance = Body()):
    logger.info(f"create_dbgpts:{gpts_instance}")
    try:
        multi_agents.gpts_create(GptsInstanceEntity(
            gpts_name=gpts_instance.gpts_name,
            gpts_describe=gpts_instance.gpts_describe,
            resource_db=json.dumps(gpts_instance.resource_db.to_dict()),
            resource_internet=json.dumps(gpts_instance.resource_internet.to_dict()),
            resource_knowledge=json.dumps(gpts_instance.resource_knowledge.to_dict()),
            gpts_agents=json.dumps(gpts_instance.gpts_agents),
            gpts_models=json.dumps(gpts_instance.gpts_models),
            language= gpts_instance.language,
            user_code=gpts_instance.user_code,
            sys_code=gpts_instance.sys_code
        ))
        return Result.succ(None)
    except Exception as e:
        logger.error(f"create_dbgpts failed:{str(e)}")
        return Result.failed(msg=str(e), code="E300002")

async def stream_generator(conv_id: str):
    async for chunk in multi_agents.chat_completions(conv_id ):
        if chunk:
            yield f"data: {json.dumps(chunk, ensure_ascii=False, cls=EnhancedJSONEncoder)}\n\n"


@router.post("/v1/dbbgpts/chat/plan/completions", response_model=Result[str])
async def dgpts_completions(gpts_name:str, user_query:str, conv_id: str = None, user_code: str = None, sys_code: str = None):
    logger.info(f"dgpts_completions:{gpts_name},{user_query},{conv_id}")
    if conv_id is None:
        conv_id = str(uuid.uuid1())
    asyncio.create_task(multi_agents.plan_chat(gpts_name, user_query, conv_id, user_code, sys_code))

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    return StreamingResponse(
        stream_generator(conv_id),
        headers=headers,
        media_type="text/plain",
    )

@router.post("/v1/dbbgpts/plan/chat/cancel", response_model=Result[str])
async def dgpts_plan_chat_cancel( conv_id: str = None, user_code: str = None, sys_code: str = None):
    pass

@router.get("/v1/dbbgpts/chat/plan/messages", response_model=Result[str])
async def plan_chat_messages( conv_id: str, user_code: str = None, sys_code: str = None):
    logger.info(f"plan_chat_messages:{conv_id},{user_code},{sys_code}")

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    return StreamingResponse(
        stream_generator(conv_id),
        headers=headers,
        media_type="text/plain",
    )





@router.post("/v1/dbbgpts/chat/feedback", response_model=Result[str])
async def dgpts_chat_feedback(filter: PagenationFilter[PluginHubFilter] = Body()):
    pass
