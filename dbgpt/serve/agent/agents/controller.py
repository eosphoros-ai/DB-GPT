import asyncio
import datetime
import json
import logging
import re
import time
import uuid
from abc import ABC
from typing import Any, Dict, List, Optional, Type

from fastapi import APIRouter, Body, Depends
from fastapi.responses import StreamingResponse

from dbgpt._private.config import Config
from dbgpt.agent import (
    Agent,
    AgentContext,
    AgentMemory,
    AutoPlanChatManager,
    ConversableAgent,
    DefaultAWELLayoutManager,
    GptsMemory,
    LLMConfig,
    ResourceType,
    ShortTermMemory,
    UserProxyAgent,
    get_agent_manager,
)
from dbgpt.agent.core.memory.gpts import GptsMessage
from dbgpt.agent.core.schema import Status
from dbgpt.agent.resource import get_resource_manager
from dbgpt.agent.util.llm.llm import LLMStrategyType
from dbgpt.app.dbgpt_server import system_app
from dbgpt.app.scene.base import ChatScene
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core import PromptTemplate
from dbgpt.core.awel.flow.flow_factory import FlowCategory
from dbgpt.core.interface.message import StorageConversation
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.model.cluster.client import DefaultLLMClient
from dbgpt.serve.conversation.serve import Serve as ConversationServe
from dbgpt.serve.prompt.api.endpoints import get_service
from dbgpt.serve.prompt.service import service as PromptService
from dbgpt.util.json_utils import serialize
from dbgpt.util.tracer import TracerManager

from ...rag.retriever.knowledge_space import KnowledgeSpaceRetriever
from ..db import GptsMessagesDao
from ..db.gpts_app import GptsApp, GptsAppDao, GptsAppQuery
from ..db.gpts_conversations_db import GptsConversationsDao, GptsConversationsEntity
from ..team.base import TeamMode
from .db_gpts_memory import MetaDbGptsMessageMemory, MetaDbGptsPlansMemory

CFG = Config()

router = APIRouter()
logger = logging.getLogger(__name__)
root_tracer: TracerManager = TracerManager()


def _build_conversation(
    conv_id: str,
    select_param: Dict[str, Any],
    model_name: str,
    summary: str,
    app_code: str,
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
        app_code=app_code,
        conv_storage=conv_serve.conv_storage,
        message_storage=conv_serve.message_storage,
    )


class MultiAgents(BaseComponent, ABC):
    name = ComponentType.MULTI_AGENTS

    def init_app(self, system_app: SystemApp):
        system_app.app.include_router(router, prefix="/api", tags=["Multi-Agents"])
        self.system_app = system_app
        from dbgpt.serve.agent.app.controller import gpts_dao

        gpts_dao.init_native_apps()

    def __init__(self, system_app: SystemApp):
        self.gpts_conversations = GptsConversationsDao()
        self.gpts_messages_dao = GptsMessagesDao()

        self.gpts_app = GptsAppDao()
        self.memory = GptsMemory(
            plans_memory=MetaDbGptsPlansMemory(),
            message_memory=MetaDbGptsMessageMemory(),
        )
        self.agent_memory_map = {}

        super().__init__(system_app)
        self.system_app = system_app

    def get_dbgpts(self, user_code: str = None, sys_code: str = None):
        apps = self.gpts_app.app_list(
            GptsAppQuery(user_code=user_code, sys_code=sys_code)
        ).app_list
        return apps

    def get_app(self, app_code) -> GptsApp:
        """get app"""
        return self.gpts_app.app_detail(app_code)

    def get_or_build_agent_memory(self, conv_id: str, dbgpts_name: str) -> AgentMemory:
        from dbgpt.agent.core.memory.hybrid import HybridMemory
        from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
        from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory

        memory_key = f"{dbgpts_name}_{conv_id}"
        if memory_key in self.agent_memory_map:
            return self.agent_memory_map[memory_key]

        # embedding_factory = EmbeddingFactory.get_instance(CFG.SYSTEM_APP)
        # embedding_fn = embedding_factory.create(
        #     model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        # )
        # vstore_name = f"_chroma_agent_memory_{dbgpts_name}_{conv_id}"
        # Just use chroma store now
        # vector_store_connector = VectorStoreConnector(
        #     vector_store_type=CFG.VECTOR_STORE_TYPE,
        #     vector_store_config=VectorStoreConfig(
        #         name=vstore_name, embedding_fn=embedding_fn
        #     ),
        # )
        # memory = HybridMemory[AgentMemoryFragment].from_chroma(
        #     vstore_name=vstore_name,
        #     embeddings=embedding_fn,
        # )

        agent_memory = AgentMemory(gpts_memory=self.memory)
        self.agent_memory_map[memory_key] = agent_memory
        return agent_memory

    async def agent_chat_v2(
        self,
        conv_id: str,
        new_order: int,
        gpts_name: str,
        user_query: str,
        user_code: str = None,
        sys_code: str = None,
        enable_verbose: bool = True,
        stream: Optional[bool] = True,
        **ext_info,
    ):
        logger.info(
            f"agent_chat_v2 conv_id:{conv_id},gpts_name:{gpts_name},user_query:{user_query}"
        )
        gpts_conversations: List[
            GptsConversationsEntity
        ] = self.gpts_conversations.get_like_conv_id_asc(conv_id)
        logger.info(
            f"gpts_conversations count:{conv_id},{len(gpts_conversations) if gpts_conversations else 0}"
        )
        gpt_chat_order = (
            "1" if not gpts_conversations else str(len(gpts_conversations) + 1)
        )
        agent_conv_id = conv_id + "_" + gpt_chat_order
        message_round = 0
        history_message_count = 0
        is_retry_chat = False
        last_speaker_name = None
        history_messages = None
        # 检查最后一个对话记录是否完成，如果是等待状态，则要继续进行当前对话
        if gpts_conversations and len(gpts_conversations) > 0:
            last_gpts_conversation: GptsConversationsEntity = gpts_conversations[-1]
            logger.info(f"last conversation status:{last_gpts_conversation.__dict__}")
            if last_gpts_conversation.state == Status.WAITING.value:
                is_retry_chat = True
                agent_conv_id = last_gpts_conversation.conv_id

                gpts_messages: List[
                    GptsMessage
                ] = self.gpts_messages_dao.get_by_conv_id(agent_conv_id)
                history_message_count = len(gpts_messages)
                history_messages = gpts_messages
                last_message = gpts_messages[-1]
                message_round = last_message.rounds + 1

                from dbgpt.serve.agent.agents.expand.app_start_assisant_agent import (
                    StartAppAssistantAgent,
                )

                if last_message.sender == StartAppAssistantAgent().role:
                    last_message = gpts_messages[-2]
                last_speaker_name = last_message.sender

                gpt_app: GptsApp = self.gpts_app.app_detail(last_message.app_code)

                if not gpt_app:
                    raise ValueError(f"Not found app {gpts_name}!")

        if not is_retry_chat:
            # 新建gpts对话记录
            gpt_app: GptsApp = self.gpts_app.app_detail(gpts_name)
            if not gpt_app:
                raise ValueError(f"Not found app {gpts_name}!")
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

        if (
            TeamMode.AWEL_LAYOUT.value == gpt_app.team_mode
            and gpt_app.team_context.flow_category == FlowCategory.CHAT_FLOW
        ):
            team_context = gpt_app.team_context
            from dbgpt.core.awel import CommonLLMHttpRequestBody

            flow_req = CommonLLMHttpRequestBody(
                model=ext_info.get("model_name", None),
                messages=user_query,
                stream=True,
                # context=flow_ctx,
                # temperature=
                # max_new_tokens=
                # enable_vis=
                conv_uid=agent_conv_id,
                span_id=root_tracer.get_current_span_id(),
                chat_mode=ext_info.get("chat_mode", None),
                chat_param=team_context.uid,
                user_name=user_code,
                sys_code=sys_code,
                incremental=ext_info.get("incremental", True),
            )
            from dbgpt.app.openapi.api_v1.api_v1 import get_chat_flow

            flow_service = get_chat_flow()
            async for chunk in flow_service.chat_stream_flow_str(
                team_context.uid, flow_req
            ):
                yield None, chunk, agent_conv_id
        else:
            # init gpts  memory
            self.memory.init(
                agent_conv_id,
                enable_vis_message=enable_verbose,
                history_messages=history_messages,
                start_round=history_message_count,
            )
            # init agent memory
            agent_memory = self.get_or_build_agent_memory(conv_id, gpts_name)

            task = None
            try:
                task = asyncio.create_task(
                    multi_agents.agent_team_chat_new(
                        user_query,
                        agent_conv_id,
                        gpt_app,
                        agent_memory,
                        is_retry_chat,
                        last_speaker_name=last_speaker_name,
                        init_message_rounds=message_round,
                        **ext_info,
                    )
                )
                if enable_verbose:
                    async for chunk in multi_agents.chat_messages(agent_conv_id):
                        if chunk:
                            try:
                                chunk = json.dumps(
                                    {"vis": chunk},
                                    default=serialize,
                                    ensure_ascii=False,
                                )
                                if chunk is None or len(chunk) <= 0:
                                    continue
                                resp = f"data:{chunk}\n\n"
                                yield task, resp, agent_conv_id
                            except Exception as e:
                                logger.exception(
                                    f"get messages {gpts_name} Exception!" + str(e)
                                )
                                yield f"data: {str(e)}\n\n"

                    yield task, f'data:{json.dumps({"vis": "[DONE]"}, default=serialize, ensure_ascii=False)} \n\n', agent_conv_id

                else:
                    logger.info(f"{agent_conv_id}开启简略消息模式，不进行vis协议封装，获取极简流式消息直接输出")
                    # 开启简略消息模式，不进行vis协议封装，获取极简流式消息直接输出
                    final_message_chunk = None
                    async for chunk in multi_agents.chat_messages(agent_conv_id):
                        if chunk:
                            try:
                                if chunk is None or len(chunk) <= 0:
                                    continue
                                final_message_chunk = chunk[-1]
                                if stream:
                                    yield task, final_message_chunk, agent_conv_id
                                logger.info(
                                    f"agent_chat_v2 executing, timestamp={int(time.time() * 1000)}"
                                )
                            except Exception as e:
                                logger.exception(
                                    f"get messages {gpts_name} Exception!" + str(e)
                                )
                                final_message_chunk = str(e)

                    logger.info(
                        f"agent_chat_v2 finish, timestamp={int(time.time() * 1000)}"
                    )
                    yield task, final_message_chunk, agent_conv_id

            except Exception as e:
                logger.exception(f"Agent chat have error!{str(e)}")
                if enable_verbose:
                    yield task, f'data:{json.dumps({"vis": f"{str(e)}"}, default=serialize, ensure_ascii=False)} \n\n', agent_conv_id
                    yield task, f'data:{json.dumps({"vis": "[DONE]"}, default=serialize, ensure_ascii=False)} \n\n', agent_conv_id
                else:
                    yield task, str(e), agent_conv_id

            finally:
                self.memory.clear(agent_conv_id)

    async def app_agent_chat(
        self,
        conv_uid: str,
        gpts_name: str,
        user_query: str,
        user_code: str = None,
        sys_code: str = None,
        enable_verbose: bool = True,
        stream: Optional[bool] = True,
        **ext_info,
    ):
        # logger.info(f"app_agent_chat:{gpts_name},{user_query},{conv_uid}")

        # Temporary compatible scenario messages
        conv_serve = ConversationServe.get_instance(CFG.SYSTEM_APP)
        current_message: StorageConversation = _build_conversation(
            conv_id=conv_uid,
            select_param=gpts_name,
            summary=user_query,
            model_name="",
            app_code=gpts_name,
            conv_serve=conv_serve,
            user_name=user_code,
        )
        current_message.save_to_storage()
        current_message.start_new_round()
        current_message.add_user_message(user_query)
        agent_conv_id = None
        agent_task = None
        default_final_message = None
        try:
            async for task, chunk, agent_conv_id in multi_agents.agent_chat_v2(
                conv_uid,
                current_message.chat_order,
                gpts_name,
                user_query,
                user_code,
                sys_code,
                enable_verbose=enable_verbose,
                stream=stream,
                **ext_info,
            ):
                agent_task = task
                default_final_message = chunk
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
            if agent_task:
                final_message = await self.stable_message(agent_conv_id)
                if final_message:
                    current_message.add_view_message(final_message)
            else:
                default_final_message = default_final_message.replace("data:", "")
                current_message.add_view_message(default_final_message)

            current_message.end_current_round()
            current_message.save_to_storage()

    async def agent_team_chat_new(
        self,
        user_query: str,
        conv_uid: str,
        gpts_app: GptsApp,
        agent_memory: AgentMemory,
        is_retry_chat: bool = False,
        last_speaker_name: str = None,
        init_message_rounds: int = 0,
        link_sender: ConversableAgent = None,
        app_link_start: bool = False,
        enable_verbose: bool = True,
        **ext_info,
    ):
        gpts_status = Status.COMPLETE.value
        try:
            employees: List[Agent] = []

            self.agent_manage = get_agent_manager()

            context: AgentContext = AgentContext(
                conv_id=conv_uid,
                gpts_app_code=gpts_app.app_code,
                gpts_app_name=gpts_app.app_name,
                language=gpts_app.language,
                app_link_start=app_link_start,
                enable_vis_message=enable_verbose,
            )

            prompt_service: PromptService = get_service()
            rm = get_resource_manager()

            # init llm provider
            ### init chat param
            worker_manager = CFG.SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
            self.llm_provider = DefaultLLMClient(
                worker_manager, auto_convert_message=True
            )

            for record in gpts_app.details:
                cls: Type[ConversableAgent] = self.agent_manage.get_by_name(
                    record.agent_name
                )
                llm_config = LLMConfig(
                    llm_client=self.llm_provider,
                    llm_strategy=LLMStrategyType(record.llm_strategy),
                    strategy_context=record.llm_strategy_value,
                )
                prompt_template = None
                if record.prompt_template:
                    prompt_template: PromptTemplate = prompt_service.get_template(
                        prompt_code=record.prompt_template
                    )
                depend_resource = rm.build_resource(record.resources, version="v1")
                agent = (
                    await cls()
                    .bind(context)
                    .bind(agent_memory)
                    .bind(llm_config)
                    .bind(depend_resource)
                    .bind(prompt_template)
                    .build(is_retry_chat=is_retry_chat)
                )
                employees.append(agent)

            team_mode = TeamMode(gpts_app.team_mode)
            if team_mode == TeamMode.SINGLE_AGENT:
                recipient = employees[0]
            else:
                if TeamMode.AUTO_PLAN == team_mode:
                    if not gpts_app.details or len(gpts_app.details) < 0:
                        raise ValueError("APP exception no available agent！")
                    llm_config = employees[0].llm_config
                    manager = AutoPlanChatManager()
                elif TeamMode.AWEL_LAYOUT == team_mode:
                    if not gpts_app.team_context:
                        raise ValueError(
                            "Your APP has not been developed yet, please bind Flow!"
                        )
                    manager = DefaultAWELLayoutManager(dag=gpts_app.team_context)
                    llm_config = LLMConfig(
                        llm_client=self.llm_provider,
                        llm_strategy=LLMStrategyType.Priority,
                        strategy_context=json.dumps(["bailing_proxyllm"]),
                    )  # TODO
                elif TeamMode.NATIVE_APP == team_mode:
                    raise ValueError(f"Native APP chat not supported!")
                else:
                    raise ValueError(f"Unknown Agent Team Mode!{team_mode}")
                manager = (
                    await manager.bind(context)
                    .bind(agent_memory)
                    .bind(llm_config)
                    .build()
                )
                manager.hire(employees)
                recipient = manager

            if is_retry_chat:
                # retry chat
                self.gpts_conversations.update(conv_uid, Status.RUNNING.value)

            user_proxy = None
            if link_sender:
                await link_sender.initiate_chat(
                    recipient=recipient,
                    message=user_query,
                    is_retry_chat=is_retry_chat,
                    last_speaker_name=last_speaker_name,
                    message_rounds=init_message_rounds,
                )
            else:
                user_proxy: UserProxyAgent = (
                    await UserProxyAgent().bind(context).bind(agent_memory).build()
                )
                await user_proxy.initiate_chat(
                    recipient=recipient,
                    message=user_query,
                    is_retry_chat=is_retry_chat,
                    last_speaker_name=last_speaker_name,
                    message_rounds=init_message_rounds,
                    **ext_info,
                )

            if user_proxy:
                # Check if the user has received a question.
                if user_proxy.have_ask_user():
                    gpts_status = Status.WAITING.value
            if not app_link_start:
                self.gpts_conversations.update(conv_uid, gpts_status)
        except Exception as e:
            logger.error(f"chat abnormal termination！{str(e)}", e)
            self.gpts_conversations.update(conv_uid, Status.FAILED.value)
        finally:
            if not app_link_start:
                await self.memory.complete(conv_uid)

        return conv_uid

    async def chat_messages(
        self,
        conv_id: str,
        user_code: str = None,
        system_app: str = None,
    ):
        while True:
            queue = self.memory.queue(conv_id)
            if not queue:
                break
            item = await queue.get()
            if item == "[DONE]":
                queue.task_done()
                break
            else:
                yield item
                await asyncio.sleep(0.005)

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
                return await self.memory.app_link_chat_message(conv_id)
            else:
                pass
                # raise ValueError(
                #     "The conversation has not been completed yet, so we cannot directly obtain information."
                # )
        else:
            raise Exception("No conversation record found!")

    def gpts_conv_list(self, user_code: str = None, system_app: str = None):
        return self.gpts_conversations.get_convs(user_code, system_app)

    async def topic_terminate(
        self,
        conv_id: str,
    ):
        gpts_conversations: List[
            GptsConversationsEntity
        ] = self.gpts_conversations.get_like_conv_id_asc(conv_id)
        # 检查最后一个对话记录是否完成，如果是等待状态，则要继续进行当前对话
        if gpts_conversations and len(gpts_conversations) > 0:
            last_gpts_conversation: GptsConversationsEntity = gpts_conversations[-1]
            if last_gpts_conversation.state == Status.WAITING.value:
                self.gpts_conversations.update(
                    last_gpts_conversation.conv_id, Status.COMPLETE.value
                )

    async def get_knowledge_resources(self, app_code: str, question: str):
        """Get the knowledge resources."""
        context = []
        app: GptsApp = self.get_app(app_code)
        if app and app.details and len(app.details) > 0:
            for detail in app.details:
                if detail and detail.resources and len(detail.resources) > 0:
                    for resource in detail.resources:
                        if resource.type == ResourceType.Knowledge:
                            retriever = KnowledgeSpaceRetriever(
                                space_id=str(resource.value),
                                top_k=CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
                            )
                            chunks = await retriever.aretrieve_with_scores(
                                question, score_threshold=0.3
                            )
                            context.extend([chunk.content for chunk in chunks])
                        else:
                            continue
        return context


multi_agents = MultiAgents(system_app)
