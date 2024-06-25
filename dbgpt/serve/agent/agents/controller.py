import asyncio
import json
import logging
import uuid
from abc import ABC
from typing import Any, Dict, List, Optional, Type

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt.agent.core.agent import Agent, AgentContext
from dbgpt.agent.core.agent_manage import get_agent_manager
from dbgpt.agent.core.base_agent import ConversableAgent
from dbgpt.agent.core.memory.agent_memory import AgentMemory
from dbgpt.agent.core.memory.gpts.gpts_memory import GptsMemory
from dbgpt.agent.core.plan import AutoPlanChatManager, DefaultAWELLayoutManager
from dbgpt.agent.core.schema import Status
from dbgpt.agent.core.user_proxy_agent import UserProxyAgent
from dbgpt.agent.resource.base import Resource
from dbgpt.agent.resource.manage import get_resource_manager
from dbgpt.agent.util.llm.llm import LLMConfig, LLMStrategyType
from dbgpt.app.openapi.api_view_model import Result
from dbgpt.app.scene.base import ChatScene
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core.interface.message import StorageConversation
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.model.cluster.client import DefaultLLMClient
from dbgpt.serve.agent.model import PagenationFilter, PluginHubFilter
from dbgpt.serve.conversation.serve import Serve as ConversationServe
from dbgpt.util.json_utils import serialize

from ..db.gpts_app import GptsApp, GptsAppDao, GptsAppQuery
from ..db.gpts_conversations_db import GptsConversationsDao, GptsConversationsEntity
from ..db.gpts_manage_db import GptsInstanceEntity
from ..team.base import TeamMode
from .db_gpts_memory import MetaDbGptsMessageMemory, MetaDbGptsPlansMemory

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
        self.gpts_conversations = GptsConversationsDao()

        self.gpts_app = GptsAppDao()
        self.memory = GptsMemory(
            plans_memory=MetaDbGptsPlansMemory(),
            message_memory=MetaDbGptsMessageMemory(),
        )
        self.agent_memory_map = {}
        super().__init__()

    def get_or_build_agent_memory(self, conv_id: str, dbgpts_name: str) -> AgentMemory:
        from dbgpt.agent.core.memory.agent_memory import (
            AgentMemory,
            AgentMemoryFragment,
        )
        from dbgpt.agent.core.memory.hybrid import HybridMemory
        from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
        from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory

        memory_key = f"{dbgpts_name}_{conv_id}"
        if memory_key in self.agent_memory_map:
            return self.agent_memory_map[memory_key]

        embedding_factory = EmbeddingFactory.get_instance(CFG.SYSTEM_APP)
        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        vstore_name = f"_chroma_agent_memory_{dbgpts_name}_{conv_id}"
        # Just use chroma store now
        # vector_store_connector = VectorStoreConnector(
        #     vector_store_type=CFG.VECTOR_STORE_TYPE,
        #     vector_store_config=VectorStoreConfig(
        #         name=vstore_name, embedding_fn=embedding_fn
        #     ),
        # )
        memory = HybridMemory[AgentMemoryFragment].from_chroma(
            vstore_name=vstore_name,
            embeddings=embedding_fn,
        )
        agent_memory = AgentMemory(memory, gpts_memory=self.memory)
        self.agent_memory_map[memory_key] = agent_memory
        return agent_memory

    def gpts_create(self, entity: GptsInstanceEntity):
        self.gpts_intance.add(entity)

    def get_dbgpts(
        self, user_code: str = None, sys_code: str = None
    ) -> Optional[List[GptsApp]]:
        apps = self.gpts_app.app_list(
            GptsAppQuery(user_code=user_code, sys_code=sys_code)
        ).app_list
        return apps

    async def agent_chat(
        self,
        agent_conv_id: str,
        gpts_name: str,
        user_query: str,
        user_code: str = None,
        sys_code: str = None,
        agent_memory: Optional[AgentMemory] = None,
    ):
        gpt_app: GptsApp = self.gpts_app.app_detail(gpts_name)

        gpts_conversation = self.gpts_conversations.get_by_conv_id(agent_conv_id)
        is_retry_chat = True
        if not gpts_conversation:
            is_retry_chat = False
            self.gpts_conversations.add(
                GptsConversationsEntity(
                    conv_id=agent_conv_id,
                    user_goal=user_query,
                    gpts_name=gpts_name,
                    team_mode=gpt_app.team_mode,
                    state=Status.RUNNING.value,
                    max_auto_reply_round=0,
                    auto_reply_count=0,
                    user_code=user_code,
                    sys_code=sys_code,
                )
            )

        task = asyncio.create_task(
            multi_agents.agent_team_chat_new(
                user_query, agent_conv_id, gpt_app, is_retry_chat, agent_memory
            )
        )

        async for chunk in multi_agents.chat_messages(agent_conv_id):
            if chunk:
                try:
                    chunk = json.dumps(
                        {"vis": chunk}, default=serialize, ensure_ascii=False
                    )
                    if chunk is None or len(chunk) <= 0:
                        continue
                    resp = f"data:{chunk}\n\n"
                    yield task, resp
                except Exception as e:
                    logger.exception(f"get messages {gpts_name} Exception!" + str(e))
                    yield f"data: {str(e)}\n\n"

        yield task, f'data:{json.dumps({"vis": "[DONE]"}, default=serialize, ensure_ascii=False)} \n\n'

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
        agent_conv_id = conv_uid + "_" + str(current_message.chat_order)
        agent_task = None
        try:
            agent_memory = self.get_or_build_agent_memory(conv_uid, gpts_name)
            agent_conv_id = conv_uid + "_" + str(current_message.chat_order)
            async for task, chunk in multi_agents.agent_chat(
                agent_conv_id,
                gpts_name,
                user_query,
                user_code,
                sys_code,
                agent_memory,
            ):
                agent_task = task
                yield chunk

        except asyncio.CancelledError:
            # Client disconnects
            print("Client disconnected")
            if agent_task:
                logger.info(f"Chat to App {gpts_name}:{agent_conv_id} Cancel!")
                agent_task.cancel()
        except Exception as e:
            logger.exception(f"Chat to App {gpts_name} Failed!" + str(e))
            raise
        finally:
            logger.info(f"save agent chat info！{conv_uid}")
            final_message = await self.stable_message(agent_conv_id)
            if final_message:
                current_message.add_view_message(final_message)
            current_message.end_current_round()
            current_message.save_to_storage()

    async def agent_team_chat_new(
        self,
        user_query: str,
        conv_uid: str,
        gpts_app: GptsApp,
        is_retry_chat: bool = False,
        agent_memory: Optional[AgentMemory] = None,
    ):
        employees: List[Agent] = []
        rm = get_resource_manager()
        context: AgentContext = AgentContext(
            conv_id=conv_uid,
            gpts_app_name=gpts_app.app_name,
            language=gpts_app.language,
        )

        # init llm provider
        ### init chat param
        worker_manager = CFG.SYSTEM_APP.get_component(
            ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
        ).create()
        self.llm_provider = DefaultLLMClient(worker_manager, auto_convert_message=True)

        depend_resource: Optional[Resource] = None
        for record in gpts_app.details:
            cls: Type[ConversableAgent] = get_agent_manager().get_by_name(
                record.agent_name
            )
            llm_config = LLMConfig(
                llm_client=self.llm_provider,
                llm_strategy=LLMStrategyType(record.llm_strategy),
                strategy_context=record.llm_strategy_value,
            )
            depend_resource = rm.build_resource(record.resources, version="v1")

            agent = (
                await cls()
                .bind(context)
                .bind(llm_config)
                .bind(depend_resource)
                .bind(agent_memory)
                .build()
            )
            employees.append(agent)

        team_mode = TeamMode(gpts_app.team_mode)
        if team_mode == TeamMode.SINGLE_AGENT:
            recipient = employees[0]
        else:
            llm_config = LLMConfig(llm_client=self.llm_provider)
            if TeamMode.AUTO_PLAN == team_mode:
                manager = AutoPlanChatManager()
            elif TeamMode.AWEL_LAYOUT == team_mode:
                manager = DefaultAWELLayoutManager(dag=gpts_app.team_context)
            else:
                raise ValueError(f"Unknown Agent Team Mode!{team_mode}")
            manager = (
                await manager.bind(context).bind(llm_config).bind(agent_memory).build()
            )
            manager.hire(employees)
            recipient = manager

        user_proxy: UserProxyAgent = (
            await UserProxyAgent().bind(context).bind(agent_memory).build()
        )
        if is_retry_chat:
            # retry chat
            self.gpts_conversations.update(conv_uid, Status.RUNNING.value)

        try:
            await user_proxy.initiate_chat(
                recipient=recipient,
                message=user_query,
            )
        except Exception as e:
            logger.error(f"chat abnormal termination！{str(e)}", e)
            self.gpts_conversations.update(conv_uid, Status.FAILED.value)

        self.gpts_conversations.update(conv_uid, Status.COMPLETE.value)
        return conv_uid

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
            message = await self.memory.one_chat_completions_v2(conv_id)
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
                return await self.memory.one_chat_completions_v2(conv_id)
            else:
                pass
                # raise ValueError(
                #     "The conversation has not been completed yet, so we cannot directly obtain information."
                # )
        else:
            raise ValueError("No conversation record found!")

    def gpts_conv_list(self, user_code: str = None, system_app: str = None):
        return self.gpts_conversations.get_convs(user_code, system_app)


multi_agents = MultiAgents()


@router.post("/v1/dbgpts/agents/list", response_model=Result[Dict[str, str]])
async def agents_list():
    logger.info("agents_list!")
    try:
        agents = get_agent_manager().all_agents()
        return Result.succ(agents)
    except Exception as e:
        return Result.failed(code="E30001", msg=str(e))


@router.get("/v1/dbgpts/list", response_model=Result[List[GptsApp]])
async def get_dbgpts(user_code: str = None, sys_code: str = None):
    logger.info(f"get_dbgpts:{user_code},{sys_code}")
    try:
        return Result.succ(multi_agents.get_dbgpts())
    except Exception as e:
        logger.error(f"get_dbgpts failed:{str(e)}")
        return Result.failed(msg=str(e), code="E300003")


@router.post("/v1/dbgpts/chat/completions", response_model=Result[str])
async def dbgpts_completions(
    gpts_name: str,
    user_query: str,
    conv_id: str = None,
    user_code: str = None,
    sys_code: str = None,
):
    logger.info(f"dbgpts_completions:{gpts_name},{user_query},{conv_id}")
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
async def dbgpts_chat_cancel(
    conv_id: str = None, user_code: str = None, sys_code: str = None
):
    pass


@router.post("/v1/dbgpts/chat/feedback", response_model=Result[str])
async def dbgpts_chat_feedback(filter: PagenationFilter[PluginHubFilter] = Body()):
    pass
