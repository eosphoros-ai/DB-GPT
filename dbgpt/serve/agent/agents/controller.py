import asyncio
import json
import logging
import uuid
from abc import ABC
from collections import defaultdict
from typing import Dict, List

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt.agent.agents.agent import Agent, AgentContext
from dbgpt.agent.agents.agents_mange import agent_mange
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.common.schema import Status
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.app.openapi.api_view_model import Result
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.model.cluster.client import DefaultLLMClient
from dbgpt.serve.agent.model import PagenationFilter, PluginHubFilter
from dbgpt.serve.agent.team.plan.team_auto_plan import AutoPlanChatManager

from ..db.gpts_conversations_db import GptsConversationsDao, GptsConversationsEntity
from ..db.gpts_mange_db import GptsInstanceDao, GptsInstanceEntity
from ..team.base import TeamMode
from ..team.layout.team_awel_layout import AwelLayoutChatManger
from .db_gpts_memory import MetaDbGptsMessageMemory, MetaDbGptsPlansMemory
from .dbgpts import DbGptsInstance

CFG = Config()


router = APIRouter()
logger = logging.getLogger(__name__)


class MultiAgents(BaseComponent, ABC):
    name = ComponentType.MULTI_AGENTS

    def init_app(self, system_app: SystemApp):
        system_app.app.include_router(router, prefix="/api", tags=["Multi-Agents"])

    def __init__(self):
        self.gpts_intance = GptsInstanceDao()
        self.gpts_conversations = GptsConversationsDao()
        self.memory = GptsMemory(
            plans_memory=MetaDbGptsPlansMemory(),
            message_memory=MetaDbGptsMessageMemory(),
        )

    def gpts_create(self, entity: GptsInstanceEntity):
        self.gpts_intance.add(entity)

    async def _build_agent_context(
        self,
        name: str,
        conv_id: str,
    ) -> AgentContext:
        gpts_instance: GptsInstanceEntity = self.gpts_intance.get_by_name(name)
        if gpts_instance is None:
            raise ValueError(f"can't find dbgpts!{name}")
        agents_names = json.loads(gpts_instance.gpts_agents)
        llm_models_priority = json.loads(gpts_instance.gpts_models)
        resource_db = (
            json.loads(gpts_instance.resource_db) if gpts_instance.resource_db else None
        )
        resource_knowledge = (
            json.loads(gpts_instance.resource_knowledge)
            if gpts_instance.resource_knowledge
            else None
        )
        resource_internet = (
            json.loads(gpts_instance.resource_internet)
            if gpts_instance.resource_internet
            else None
        )
        ### init chat param
        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        llm_task = DefaultLLMClient(worker_manager)
        context: AgentContext = AgentContext(conv_id=conv_id, llm_provider=llm_task)
        context.gpts_name = gpts_instance.gpts_name
        context.resource_db = resource_db
        context.resource_internet = resource_internet
        context.resource_knowledge = resource_knowledge
        context.agents = agents_names

        context.llm_models = await llm_task.models()
        context.model_priority = llm_models_priority
        return context

    async def _build_chat_manger(
        self, context: AgentContext, mode: TeamMode, agents: List[Agent]
    ):
        if mode == TeamMode.SINGLE_AGENT:
            manager = agents[0]
        else:
            if TeamMode.AUTO_PLAN == mode:
                manager = AutoPlanChatManager(
                    agent_context=context,
                    memory=self.memory,
                    plan_chat=groupchat,
                    planner=planner,
                )
            elif TeamMode.AWEL_LAYOUT == mode:
                manager = AwelLayoutChatManger(
                    agent_context=context,
                    memory=self.memory,
                )
            else:
                raise ValueError(f"Unknown Agent Team Mode!{mode}")
            manager.hire(agents)

        return manager

    async def agent_team_chat(
        self,
        name: str,
        mode: TeamMode,
        user_query: str,
        conv_id: str,
        user_code: str = None,
        sys_code: str = None,
    ):
        """Initiate an Agent-based conversation
        Args:
            name:
            mode:
            user_query:
            conv_id:
            user_code:
            sys_code:

        Returns:

        """
        context = await self._build_agent_context(name, conv_id)
        agent_map = defaultdict()
        agents = []
        for name in context.agents:
            cls = agent_mange.get_by_name(name)
            agent = cls(
                agent_context=context,
                memory=self.memory,
            )
            agents.append(agent)

        manager = await self._build_chat_manger(context, mode, agents)
        user_proxy = UserProxyAgent(memory=self.memory, agent_context=context)

        gpts_conversation = self.gpts_conversations.get_by_conv_id(conv_id)
        if gpts_conversation is None:
            self.gpts_conversations.add(
                GptsConversationsEntity(
                    conv_id=conv_id,
                    user_goal=user_query,
                    gpts_name=name,
                    state=Status.RUNNING.value,
                    max_auto_reply_round=context.max_chat_round,
                    auto_reply_count=0,
                    user_code=user_code,
                    sys_code=sys_code,
                )
            )

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
                await user_proxy.a_retry_chat(
                    recipient=manager,
                    memory=self.memory,
                )
            except Exception as e:
                logger.error(f"chat abnormal termination！{str(e)}", e)
                self.gpts_conversations.update(conv_id, Status.FAILED.value)

        self.gpts_conversations.update(conv_id, Status.COMPLETE.value)
        return conv_id

    async def plan_chat(
        self,
        name: str,
        user_query: str,
        conv_id: str,
        user_code: str = None,
        sys_code: str = None,
    ):
        context = await self._build_agent_context(name, conv_id)

        ### default plan excute mode
        agents = []
        for name in context.agents:
            cls = agent_mange.get_by_name(name)
            agent = cls(
                agent_context=context,
                memory=self.memory,
            )
            agents.append(agent)
            agent_map[name] = agent

        manager = AutoPlanChatManager(
            agent_context=context,
            memory=self.memory,
        )
        manager.hire(agents)

        user_proxy = UserProxyAgent(memory=self.memory, agent_context=context)

        gpts_conversation = self.gpts_conversations.get_by_conv_id(conv_id)
        if gpts_conversation is None:
            self.gpts_conversations.add(
                GptsConversationsEntity(
                    conv_id=conv_id,
                    user_goal=user_query,
                    gpts_name=name,
                    state=Status.RUNNING.value,
                    max_auto_reply_round=context.max_chat_round,
                    auto_reply_count=0,
                    user_code=user_code,
                    sys_code=sys_code,
                )
            )

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
                await user_proxy.a_retry_chat(
                    recipient=manager,
                    memory=self.memory,
                )
            except Exception as e:
                logger.error(f"chat abnormal termination！{str(e)}", e)
                self.gpts_conversations.update(conv_id, Status.FAILED.value)

        self.gpts_conversations.update(conv_id, Status.COMPLETE.value)
        return conv_id

    async def chat_completions(
        self, conv_id: str, user_code: str = None, system_app: str = None
    ):
        is_complete = False
        while True:
            gpts_conv = self.gpts_conversations.get_by_conv_id(conv_id)
            if gpts_conv:
                is_complete = (
                    True
                    if gpts_conv.state
                    in [
                        Status.COMPLETE.value,
                        Status.WAITING.value,
                        Status.FAILED.value,
                    ]
                    else False
                )
            yield await self.memory.one_plan_chat_competions(conv_id)
            if is_complete:
                return
            else:
                await asyncio.sleep(5)

    async def stable_message(
        self, conv_id: str, user_code: str = None, system_app: str = None
    ):
        gpts_conv = self.gpts_conversations.get_by_conv_id(conv_id)
        if gpts_conv:
            is_complete = (
                True
                if gpts_conv.state
                in [Status.COMPLETE.value, Status.WAITING.value, Status.FAILED.value]
                else False
            )
            if is_complete:
                return await self.self.memory.one_plan_chat_competions(conv_id)
            else:
                raise ValueError(
                    "The conversation has not been completed yet, so we cannot directly obtain information."
                )
        else:
            raise ValueError("No conversation record found!")

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
        multi_agents.gpts_create(
            GptsInstanceEntity(
                gpts_name=gpts_instance.gpts_name,
                gpts_describe=gpts_instance.gpts_describe,
                resource_db=json.dumps(gpts_instance.resource_db.to_dict()),
                resource_internet=json.dumps(gpts_instance.resource_internet.to_dict()),
                resource_knowledge=json.dumps(
                    gpts_instance.resource_knowledge.to_dict()
                ),
                gpts_agents=json.dumps(gpts_instance.gpts_agents),
                gpts_models=json.dumps(gpts_instance.gpts_models),
                language=gpts_instance.language,
                user_code=gpts_instance.user_code,
                sys_code=gpts_instance.sys_code,
            )
        )
        return Result.succ(None)
    except Exception as e:
        logger.error(f"create_dbgpts failed:{str(e)}")
        return Result.failed(msg=str(e), code="E300002")


async def stream_generator(conv_id: str):
    async for chunk in multi_agents.chat_completions(conv_id):
        if chunk:
            yield f"data: {chunk}\n\n"


@router.post("/v1/dbbgpts/chat/plan/completions", response_model=Result[str])
async def dgpts_completions(
    gpts_name: str,
    user_query: str,
    conv_id: str = None,
    user_code: str = None,
    sys_code: str = None,
):
    logger.info(f"dgpts_completions:{gpts_name},{user_query},{conv_id}")
    if conv_id is None:
        conv_id = str(uuid.uuid1())
    asyncio.create_task(
        multi_agents.plan_chat(gpts_name, user_query, conv_id, user_code, sys_code)
    )

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
async def dgpts_plan_chat_cancel(
    conv_id: str = None, user_code: str = None, sys_code: str = None
):
    pass


@router.get("/v1/dbbgpts/chat/plan/messages", response_model=Result[str])
async def plan_chat_messages(conv_id: str, user_code: str = None, sys_code: str = None):
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
