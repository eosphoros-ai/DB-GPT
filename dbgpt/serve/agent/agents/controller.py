import asyncio
import json
import logging
import uuid
from abc import ABC
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt.agent.agents.agent import Agent, AgentContext
from dbgpt.agent.agents.agents_manage import agent_manage
from dbgpt.agent.agents.user_proxy_agent import UserProxyAgent
from dbgpt.agent.common.schema import Status
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.app.openapi.api_view_model import Result
from dbgpt.app.scene.base import ChatScene
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core.interface.message import StorageConversation
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.model.cluster.client import DefaultLLMClient
from dbgpt.serve.agent.model import PagenationFilter, PluginHubFilter
from dbgpt.serve.agent.team.plan.team_auto_plan import AutoPlanChatManager
from dbgpt.serve.conversation.serve import Serve as ConversationServe
from dbgpt.util.json_utils import serialize

from ..db.gpts_conversations_db import GptsConversationsDao, GptsConversationsEntity
from ..db.gpts_manage_db import GptsInstanceDao, GptsInstanceEntity
from ..team.base import TeamMode
from ..team.layout.team_awel_layout import AwelLayoutChatManager
from .db_gpts_memory import MetaDbGptsMessageMemory, MetaDbGptsPlansMemory
from .dbgpts import DbGptsInstance

CFG = Config()


router = APIRouter()
logger = logging.getLogger(__name__)


def _build_conversation(
    conv_id: str,
    select_param: Dict[str, Any],
    model_name: str,
    summary: str,
    conv_serve: ConversationServe,
    user_name: Optional[str] = "",
    sys_code: Optional[str] = "",
) -> StorageConversation:
    return StorageConversation(
        conv_uid=conv_id,
        chat_mode=ChatScene.ChatAgent.value(),
        user_name=user_name,
        sys_code=sys_code,
        model_name=model_name,
        summary=summary,
        param_type="DbGpts",
        param_value=select_param,
        conv_storage=conv_serve.conv_storage,
        message_storage=conv_serve.message_storage,
    )


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

    def get_dbgpts(self, user_code: str = None, sys_code: str = None):
        return self.gpts_intance.get_by_user(user_code, sys_code)

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
        return context, gpts_instance.team_mode

    async def _build_chat_manager(
        self, context: AgentContext, mode: TeamMode, agents: List[Agent]
    ):
        if mode == TeamMode.SINGLE_AGENT:
            manager = agents[0]
        else:
            if TeamMode.AUTO_PLAN == mode:
                manager = AutoPlanChatManager(
                    agent_context=context,
                    memory=self.memory,
                )
            elif TeamMode.AWEL_LAYOUT == mode:
                manager = AwelLayoutChatManager(
                    agent_context=context,
                    memory=self.memory,
                )
            else:
                raise ValueError(f"Unknown Agent Team Mode!{mode}")
            manager.hire(agents)

        return manager

    async def agent_chat(
        self,
        agent_conv_id: str,
        gpts_name: str,
        user_query: str,
        user_code: str = None,
        sys_code: str = None,
    ):
        context, team_mode = await self._build_agent_context(gpts_name, agent_conv_id)
        gpts_conversation = self.gpts_conversations.get_by_conv_id(agent_conv_id)
        is_retry_chat = True
        if not gpts_conversation:
            is_retry_chat = False
            self.gpts_conversations.add(
                GptsConversationsEntity(
                    conv_id=agent_conv_id,
                    user_goal=user_query,
                    gpts_name=gpts_name,
                    state=Status.RUNNING.value,
                    max_auto_reply_round=context.max_chat_round,
                    auto_reply_count=0,
                    user_code=user_code,
                    sys_code=sys_code,
                )
            )

        asyncio.create_task(
            multi_agents.agent_team_chat(user_query, context, team_mode, is_retry_chat)
        )

        # def task_done_callback(task):
        #     if task.cancelled():
        #         logger.warning("The task was cancelled!")
        #     elif task.exception():
        #         logger.exception(f"The task raised an exception: {task.exception()}")
        #     else:
        #         logger.info(f"Callback: {task.result()}")
        #         loop = asyncio.get_event_loop()
        #         future = asyncio.run_coroutine_threadsafe(
        #             self.stable_message(agent_conv_id), loop
        #         )
        #
        #         current_message.add_view_message(future.result())
        #         current_message.end_current_round()
        #     current_message.save_to_storage()
        #
        # task.add_done_callback(task_done_callback)
        async for chunk in multi_agents.chat_messages(agent_conv_id):
            if chunk:
                logger.info(chunk)
                try:
                    chunk = json.dumps(
                        {"vis": chunk}, default=serialize, ensure_ascii=False
                    )
                    yield f"data: {chunk}\n\n"
                except Exception as e:
                    logger.exception(f"get messages {gpts_name} Exception!" + str(e))
                    yield f"data: {str(e)}\n\n"

        yield f'data:{json.dumps({"vis": "[DONE]"}, default=serialize, ensure_ascii=False)} \n\n'

    async def app_agent_chat(
        self,
        conv_uid: str,
        gpts_name: str,
        user_query: str,
        user_code: str = None,
        sys_code: str = None,
    ):
        logger.info(f"app_agent_chat:{gpts_name},{user_query},{conv_uid}")

        # Temporary compatible scenario messages
        conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)
        current_message: StorageConversation = _build_conversation(
            conv_id=conv_uid,
            select_param=gpts_name,
            summary=user_query,
            model_name="",
            conv_serve=conv_serve,
        )

        current_message.save_to_storage()
        current_message.start_new_round()
        current_message.add_user_message(user_query)
        try:
            agent_conv_id = conv_uid + "_" + str(current_message.chat_order)
            async for chunk in multi_agents.agent_chat(
                agent_conv_id, gpts_name, user_query, user_code, sys_code
            ):
                yield chunk

            final_message = await self.stable_message(agent_conv_id)
        except Exception as e:
            logger.exception(f"Chat to App {gpts_name} Failed!" + str(e))
        finally:
            logger.info(f"save agent chat info！{conv_uid},{agent_conv_id}")
            current_message.add_view_message(final_message)
            current_message.end_current_round()
            current_message.save_to_storage()

    async def agent_team_chat(
        self,
        user_query: str,
        context: AgentContext,
        team_mode: TeamMode,
        is_retry_chat: bool = False,
    ):
        """Initiate an Agent-based conversation
        Args:
            user_query:
            context:
            team_mode:
            is_retry_chat:

        Returns:

        """
        try:
            agents = []
            for name in context.agents:
                cls = agent_manage.get_by_name(name)
                agent = cls(
                    agent_context=context,
                    memory=self.memory,
                )
                agents.append(agent)

            manager = await self._build_chat_manager(
                context, TeamMode(team_mode), agents
            )
            user_proxy = UserProxyAgent(memory=self.memory, agent_context=context)

            if not is_retry_chat:
                ## dbgpts conversation save
                try:
                    await user_proxy.a_initiate_chat(
                        recipient=manager,
                        message=user_query,
                        memory=self.memory,
                    )
                except Exception as e:
                    logger.error(f"chat abnormal termination！{str(e)}", e)
                    self.gpts_conversations.update(context.conv_id, Status.FAILED.value)

            else:
                # retry chat
                self.gpts_conversations.update(context.conv_id, Status.RUNNING.value)
                try:
                    await user_proxy.a_retry_chat(
                        recipient=manager,
                        memory=self.memory,
                    )
                except Exception as e:
                    logger.error(f"chat abnormal termination！{str(e)}", e)
                    self.gpts_conversations.update(context.conv_id, Status.FAILED.value)

            self.gpts_conversations.update(context.conv_id, Status.COMPLETE.value)
            return context.conv_id
        except Exception as e:
            logger.exception("new chat compeletion failed!")
            self.gpts_conversations.update(context.conv_id, Status.FAILED.value)
            raise ValueError(f"Add chat failed!{str(e)}")

    async def chat_messages(
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
            message = await self.memory.one_chat_competions(conv_id)
            yield message

            if is_complete:
                break
            else:
                await asyncio.sleep(2)

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
                return await self.memory.one_chat_competions(conv_id)
            else:
                raise ValueError(
                    "The conversation has not been completed yet, so we cannot directly obtain information."
                )
        else:
            raise ValueError("No conversation record found!")

    def gpts_conv_list(self, user_code: str = None, system_app: str = None):
        return self.gpts_conversations.get_convs(user_code, system_app)


multi_agents = MultiAgents()


@router.post("/v1/dbgpts/agents/list", response_model=Result[str])
async def agents_list():
    logger.info("agents_list!")
    try:
        agents = agent_manage.all_agents()
        return Result.succ(agents)
    except Exception as e:
        return Result.failed(code="E30001", msg=str(e))


@router.post("/v1/dbgpts/create", response_model=Result[str])
async def create_dbgpts(gpts_instance: DbGptsInstance = Body()):
    logger.info(f"create_dbgpts:{gpts_instance}")
    try:
        multi_agents.gpts_create(
            GptsInstanceEntity(
                gpts_name=gpts_instance.gpts_name,
                gpts_describe=gpts_instance.gpts_describe,
                team_mode=gpts_instance.team_mode,
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


@router.get("/v1/dbgpts/list", response_model=Result[str])
async def get_dbgpts(user_code: str = None, sys_code: str = None):
    logger.info(f"get_dbgpts:{user_code},{sys_code}")
    try:
        return Result.succ(multi_agents.get_dbgpts())
    except Exception as e:
        logger.error(f"get_dbgpts failed:{str(e)}")
        return Result.failed(msg=str(e), code="E300003")


@router.post("/v1/dbgpts/chat/completions", response_model=Result[str])
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

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Transfer-Encoding": "chunked",
    }
    return StreamingResponse(
        multi_agents.agent_chat(
            agent_conv_id=conv_id,
            gpts_name=gpts_name,
            user_query=user_query,
            user_code=user_code,
            sys_code=sys_code,
        ),
        headers=headers,
        media_type="text/plain",
    )


@router.post("/v1/dbgpts/chat/cancel", response_model=Result[str])
async def dgpts_chat_cancel(
    conv_id: str = None, user_code: str = None, sys_code: str = None
):
    pass


@router.post("/v1/dbgpts/chat/feedback", response_model=Result[str])
async def dgpts_chat_feedback(filter: PagenationFilter[PluginHubFilter] = Body()):
    pass
