import logging
import json
import asyncio
import uuid
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

from .dbgpts import DbGptsCompletion, DbGptsTaskStep, DbGptsMessage

from dbgpt.configs.model_config import PLUGINS_DIR
from dbgpt.component import BaseComponent, ComponentType, SystemApp

router = APIRouter()
logger = logging.getLogger(__name__)


class MultiAgents(BaseComponent, ABC):
    name = ComponentType.MULTI_AGENTS

    def init_app(self, system_app: SystemApp):
        system_app.app.include_router(router, prefix="/api", tags=["Multi-Agents"])

    def __init__(self):
        self.gpts_intance = GptsInstanceDao()
        self.gpts_conversations = GptsConversationsDao()
        self.agent_mange = AgentsMange()
        self.memory = GptsMemory(plans_memory=MetaDbGptsPlansMemory(), message_memory=MetaDbGptsMessageMemory())

    def gpts_create(self, gpts_context):
        self.gpts_intance.add(GptsInstanceEntity(**gpts_context))

    def chat_start(self, name: str, user_query: str, user_code: str = None, system_app: str = None):
        gpts_instance: GptsInstanceEntity = self.gpts_intance.get_by_name(name)
        agents_name = gpts_instance.gpts_agents.spilt(",")
        llm_models = gpts_instance.gpts_models.spilt(",")
        resource_db = json.loads(gpts_instance.resource_db) if gpts_instance.resource_db else None
        resource_knowledge = json.loads(gpts_instance.resource_knowledge) if gpts_instance.resource_knowledge else None
        resource_internet = json.loads(gpts_instance.resource_internet) if gpts_instance.resource_internet else None

        ### init chat param
        conv_id = uuid.uuid1()
        context: AgentContext = AgentContext(conv_id=conv_id, gpts_name=gpts_instance.gpts_name)
        context.resource_db = resource_db
        context.resource_internet = resource_internet
        context.resource_knowledge = resource_knowledge
        context.agents = agents_name
        context.llm_models = llm_models

        self.gpts_conversations.add(GptsConversationsEntity(
            conv_id=conv_id,
            user_goal=user_query,
            gpts_name=gpts_instance.gpts_name,
            state=Status.RUNNING.value,
            max_auto_reply_round=context.max_chat_round,
            auto_reply_count=0,
            user_code=user_code,
            system_app=system_app
        ))

        ### default plan excute mode
        agents = []
        for name in agents_name:
            cls = self.agent_mange.get_by_name(name)
            agents.append(cls(agent_context=context, memory=self.memory))
        groupchat = PlanChat(agents=agents, messages=[], max_round=50)

        planner = PlannerAgent(
            agent_context=context,
            memory=self.memory,
            plan_chat=groupchat,
        )
        manager = PlanChatManager(plan_chat=groupchat, planner=planner, agent_context=context, memory=self.memory)

        user_proxy = UserProxyAgent(
            memory=self.memory,
            agent_context=context
        )

        ## dbgpts conversation save

        user_proxy.a_initiate_chat(
            recipient=manager,
            message=user_query,
            memory=self.memory,
        )
        return conv_id

    async def chat_completions(self, conv_id: str, user_code: str = None, system_app: str = None):
        is_complete = False
        while True:
            if is_complete:
                return

            plans = self.memory.plans_memory.get_by_conv_id(conv_id=conv_id)
            messages = self.memory.message_memory.get_by_conv_id(conv_id=conv_id)

            task_steps = []
            for plan in plans:
                task_steps.append(DbGptsTaskStep(
                    task_num=plan.sub_task_num,
                    task_content=plan.sub_task_content,
                    state=plan.state,
                    result=plan.result,
                    agent_name=plan.sub_task_agent,
                    model_name=plan.agent_model
                ))

            dbgpts_messages = []
            for message in messages:
                dbgpts_messages.append(DbGptsMessage(
                    sender=message.sender,
                    reciver=message.reciver,
                    content=message.content,
                    action_report=message.action_report
                ))

            completion = DbGptsCompletion(
                conv_id=conv_id,
                task_steps=task_steps,
                messages=dbgpts_messages
            )

            yield completion
            await asyncio.sleep(1)

    def gpts_conv_list(self, user_code: str = None, system_app: str = None):
        return self.gpts_conversations.get_convs(user_code, system_app)


multi_agents = MultiAgents()


@router.post("/v1/dbbgpts/agents/list", response_model=Result[str])
async def agents_list():
    logger.info("agents_list!")
    try:
        return Result.success(multi_agents.agent_mange.all_agents())
    except Exception as e:
        return Result.failed(str(e))

@router.post("/v1/dbbgpts/create", response_model=Result[str])
async def create_dbgpts(gpts_context: dict = Body()):
    logger.info(f"create_dbgpts:{gpts_context}")
    try:
        return Result.success(multi_agents.gpts_create(gpts_context))
    except Exception as e:
        return Result.failed(str(e))

async def stream_generator(conv_id: str):
    async for chunk in multi_agents.chat_completions(conv_id ):
        if chunk:
            yield f"data: {json.dumps(chunk, ensure_ascii=False, cls=EnhancedJSONEncoder)}\n\n"


@router.post("/v1/dbbgpts/chat/completions", response_model=Result[str])
async def dgpts_completions(gpts_dialogue: dict = Body()):
    logger.info(f"dgpts_completions:{gpts_dialogue}")
    try:
        conv_id = multi_agents.chat_start(gpts_dialogue.get('gpts_name'), gpts_dialogue.get('user_query'), gpts_dialogue.get('user_code', None), gpts_dialogue.get('system_app', None))

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
    except Exception as e:
        return Result.failed(str(e))



@router.post("/v1/dbbgpts/chat/feedback", response_model=Result[str])
async def dgpts_chat_feedback(filter: PagenationFilter[PluginHubFilter] = Body()):
    pass
