import asyncio
import json
import logging
import time
from abc import ABC
from copy import deepcopy
from typing import Any, Dict, List, Optional, Type

from fastapi import APIRouter

from dbgpt._private.config import Config
from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    AutoPlanChatManager,
    ConversableAgent,
    EnhancedShortTermMemory,
    HybridMemory,
    LLMConfig,
    ResourceType,
    UserProxyAgent,
    get_agent_manager,
)
from dbgpt.agent.core.base_team import ManagerAgent
from dbgpt.agent.core.memory.gpts import GptsMessage
from dbgpt.agent.core.schema import Status
from dbgpt.agent.resource import ResourceManager, get_resource_manager
from dbgpt.agent.util.llm.strategy_manage import LLMStrategyType
from dbgpt.component import BaseComponent, ComponentType, SystemApp
from dbgpt.core import PromptTemplate
from dbgpt.core.awel.flow.flow_factory import FlowCategory
from dbgpt.core.interface.message import StorageConversation
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.model.cluster.client import DefaultLLMClient
from dbgpt.util.executor_utils import ExecutorFactory
from dbgpt.util.json_utils import serialize
from dbgpt.util.tracer import TracerManager
from dbgpt_app.dbgpt_server import system_app
from dbgpt_app.scene.base import ChatScene
from dbgpt_serve.conversation.serve import Serve as ConversationServe
from dbgpt_serve.core import blocking_func_to_async
from dbgpt_serve.prompt.api.endpoints import get_service
from dbgpt_serve.prompt.service import service as PromptService

from ...rag.retriever.knowledge_space import KnowledgeSpaceRetriever
from ..db import GptsMessagesDao
from ..db.gpts_app import GptsApp, GptsAppDao, GptsAppDetail, GptsAppQuery
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

    def __init__(self, system_app: SystemApp):
        self.gpts_conversations = GptsConversationsDao()
        self.gpts_messages_dao = GptsMessagesDao()

        self.gpts_app = GptsAppDao()
        from dbgpt.agent.core.memory.gpts.disk_cache_gpts_memory import (
            DiskCacheGptsMemory,
        )

        self.memory = DiskCacheGptsMemory(
            plans_memory=MetaDbGptsPlansMemory(),
            message_memory=MetaDbGptsMessageMemory(),
        )
        self.agent_memory_map = {}

        super().__init__(system_app)
        self.system_app = system_app

    def on_init(self):
        """Called when init the application.

        Import your own module here to ensure the module is loaded before the
        application starts
        """
        from ..db.gpts_app import (  # noqa: F401
            GptsAppCollectionEntity,
            GptsAppDetailEntity,
            GptsAppEntity,
            UserRecentAppsEntity,
        )

    def after_start(self):
        from dbgpt_serve.agent.app.controller import gpts_dao

        gpts_dao.init_native_apps()

        gpts_dao.init_native_apps("dbgpt")

    def get_dbgpts(self, user_code: str = None, sys_code: str = None):
        apps = self.gpts_app.app_list(
            GptsAppQuery(user_code=user_code, sys_code=sys_code)
        ).app_list
        return apps

    def get_app(self, app_code) -> GptsApp:
        """get app"""
        return self.gpts_app.app_detail(app_code)

    def get_or_build_agent_memory(self, conv_id: str, dbgpts_name: str) -> AgentMemory:
        from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
        from dbgpt_serve.rag.storage_manager import StorageManager

        executor = self.system_app.get_component(
            ComponentType.EXECUTOR_DEFAULT, ExecutorFactory
        ).create()

        storage_manager = StorageManager.get_instance(self.system_app)
        index_name = "agent_memory_long_term"
        vector_store = storage_manager.create_vector_store(index_name=index_name)
        if not vector_store.vector_name_exists():
            vector_store.create_collection(collection_name=index_name)
        embeddings = EmbeddingFactory.get_instance(self.system_app).create()
        short_term_memory = EnhancedShortTermMemory(
            embeddings, executor=executor, buffer_size=10
        )
        memory = HybridMemory.from_vstore(
            vector_store,
            embeddings=embeddings,
            executor=executor,
            short_term_memory=short_term_memory,
        )
        agent_memory = AgentMemory(memory, gpts_memory=self.memory)

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
            f"agent_chat_v2 conv_id:{conv_id},gpts_name:{gpts_name},user_query:"
            f"{user_query}"
        )
        gpts_conversations: List[GptsConversationsEntity] = (
            self.gpts_conversations.get_like_conv_id_asc(conv_id)
        )

        logger.info(
            f"gpts_conversations count:{conv_id}, "
            f"{len(gpts_conversations) if gpts_conversations else 0}"
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

                gpts_messages: List[GptsMessage] = (
                    self.gpts_messages_dao.get_by_conv_id(agent_conv_id)
                )
                history_message_count = len(gpts_messages)
                history_messages = gpts_messages
                last_message = gpts_messages[-1]
                message_round = last_message.rounds + 1

                from dbgpt_serve.agent.agents.expand.app_start_assisant_agent import (
                    StartAppAssistantAgent,
                )

                if last_message.sender == StartAppAssistantAgent().role:
                    last_message = gpts_messages[-2]
                last_speaker_name = last_message.sender

                gpt_app: GptsApp = self.gpts_app.app_detail(last_message.app_code)

                if not gpt_app:
                    raise ValueError(f"Not found app {gpts_name}!")

        historical_dialogues: List[GptsMessage] = []
        if not is_retry_chat:
            # Create a new gpts conversation record
            gpt_app: GptsApp = self.gpts_app.app_detail(gpts_name)
            if not gpt_app:
                raise ValueError(f"Not found app {gpts_name}!")

            ## When creating a new gpts conversation record, determine whether to
            # include the history of previous topics according to the application
            # definition.
            ## TODO BEGIN
            # Temporarily use system configuration management, and subsequently use
            # application configuration management
            if CFG.MESSAGES_KEEP_START_ROUNDS and CFG.MESSAGES_KEEP_START_ROUNDS > 0:
                gpt_app.keep_start_rounds = CFG.MESSAGES_KEEP_START_ROUNDS
            if CFG.MESSAGES_KEEP_END_ROUNDS and CFG.MESSAGES_KEEP_END_ROUNDS > 0:
                gpt_app.keep_end_rounds = CFG.MESSAGES_KEEP_END_ROUNDS
            ## TODO END

            if gpt_app.keep_start_rounds > 0 or gpt_app.keep_end_rounds > 0:
                if gpts_conversations and len(gpts_conversations) > 0:
                    rely_conversations = []
                    if gpt_app.keep_start_rounds + gpt_app.keep_end_rounds < len(
                        gpts_conversations
                    ):
                        if gpt_app.keep_start_rounds > 0:
                            front = gpts_conversations[gpt_app.keep_start_rounds :]
                            rely_conversations.extend(front)
                        if gpt_app.keep_end_rounds > 0:
                            back = gpts_conversations[-gpt_app.keep_end_rounds :]
                            rely_conversations.extend(back)
                    else:
                        rely_conversations = gpts_conversations
                    for gpts_conversation in rely_conversations:
                        temps: List[GptsMessage] = await self.memory.get_messages(
                            gpts_conversation.conv_id
                        )
                        if temps and len(temps) > 1:
                            historical_dialogues.append(temps[0])
                            historical_dialogues.append(temps[-1])

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
            from dbgpt_app.openapi.api_v1.api_v1 import get_chat_flow

            flow_service = get_chat_flow()
            async for chunk in flow_service.chat_stream_flow_str(
                team_context.uid, flow_req
            ):
                yield None, chunk, agent_conv_id
        else:
            # init gpts  memory
            vis_protocal = None
            # if enable_verbose:
            ## Defaul use gpt_vis ui component‘s package
            from dbgpt_ext.vis.gpt_vis.gpt_vis_converter_v2 import GptVisConverterNew

            vis_protocal = GptVisConverterNew()

            self.memory.init(
                agent_conv_id,
                history_messages=history_messages,
                start_round=history_message_count,
                vis_converter=vis_protocal,
            )
            # init agent memory
            agent_memory = self.get_or_build_agent_memory(conv_id, gpts_name)

            task = None
            try:
                task = asyncio.create_task(
                    multi_agents.agent_team_chat_new(
                        user_query,
                        agent_conv_id,
                        conv_id,
                        gpt_app,
                        agent_memory,
                        is_retry_chat,
                        last_speaker_name=last_speaker_name,
                        init_message_rounds=message_round,
                        enable_verbose=enable_verbose,
                        historical_dialogues=historical_dialogues,
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

                    yield (
                        task,
                        _format_vis_msg("[DONE]"),
                        agent_conv_id,
                    )

                else:
                    logger.info(
                        f"{agent_conv_id}开启简略消息模式，不进行vis协议封装，获取极简流式消息直接输出"
                    )
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
                                    "agent_chat_v2 executing, timestamp="
                                    f"{int(time.time() * 1000)}"
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
                    yield (
                        task,
                        _format_vis_msg("[DONE]"),
                        agent_conv_id,
                    )
                    yield (
                        task,
                        _format_vis_msg("[DONE]"),
                        agent_conv_id,
                    )
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

    async def _build_agent_by_gpts(
        self,
        context: AgentContext,
        agent_memory: AgentMemory,
        rm: ResourceManager,
        app: GptsApp,
    ) -> ConversableAgent:
        """Build a dialogue target agent through gpts configuration"""
        logger.info(f"_build_agent_by_gpts:{app.app_code},{app.app_name}")
        employees: List[ConversableAgent] = []
        if app.details is not None and len(app.details) > 0:
            employees: List[ConversableAgent] = await self._build_employees(
                context, agent_memory, rm, [deepcopy(item) for item in app.details]
            )
        team_mode = TeamMode(app.team_mode)
        prompt_service: PromptService = get_service()
        if team_mode == TeamMode.SINGLE_AGENT:
            if employees is not None and len(employees) == 1:
                recipient = employees[0]
            else:
                single_context = app.team_context
                cls: Type[ConversableAgent] = self.agent_manage.get_by_name(
                    single_context.agent_name
                )

                llm_config = LLMConfig(
                    llm_client=self.llm_provider,
                    lm_strategy=LLMStrategyType(single_context.llm_strategy),
                    strategy_context=single_context.llm_strategy_value,
                )
                prompt_template = None
                if single_context.prompt_template:
                    prompt_template: PromptTemplate = prompt_service.get_template(
                        prompt_code=single_context.prompt_template
                    )
                depend_resource = await blocking_func_to_async(
                    CFG.SYSTEM_APP, rm.build_resource, single_context.resources
                )

                recipient = (
                    await cls()
                    .bind(context)
                    .bind(agent_memory)
                    .bind(llm_config)
                    .bind(depend_resource)
                    .bind(prompt_template)
                    .build()
                )
                recipient.profile.name = app.app_name
                recipient.profile.desc = app.app_describe
                recipient.profile.avatar = app.icon
            return recipient
        elif TeamMode.AUTO_PLAN == team_mode:
            if app.team_context:
                agent_manager = get_agent_manager()
                auto_team_ctx = app.team_context

                manager_cls: Type[ConversableAgent] = agent_manager.get_by_name(
                    auto_team_ctx.teamleader
                )
                manager = manager_cls()
                if isinstance(manager, ManagerAgent) and len(employees) > 0:
                    manager.hire(employees)

                llm_config = LLMConfig(
                    llm_client=self.llm_provider,
                    llm_strategy=LLMStrategyType(auto_team_ctx.llm_strategy),
                    strategy_context=auto_team_ctx.llm_strategy_value,
                )
                manager.bind(llm_config)

                if auto_team_ctx.prompt_template:
                    prompt_template: PromptTemplate = prompt_service.get_template(
                        prompt_code=auto_team_ctx.prompt_template
                    )
                    manager.bind(prompt_template)
                if auto_team_ctx.resources:
                    depend_resource = await blocking_func_to_async(
                        CFG.SYSTEM_APP, rm.build_resource, auto_team_ctx.resources
                    )
                    manager.bind(depend_resource)

                manager = await manager.bind(context).bind(agent_memory).build()
            else:
                ## default
                manager = AutoPlanChatManager()
                llm_config = employees[0].llm_config

                if not employees or len(employees) < 0:
                    raise ValueError("APP exception no available agent！")
                manager = (
                    await manager.bind(context)
                    .bind(agent_memory)
                    .bind(llm_config)
                    .build()
                )
                manager.hire(employees)

            manager.profile.name = app.app_name
            manager.profile.desc = app.app_describe
            manager.profile.avatar = app.icon
            logger.info(
                f"_build_agent_by_gpts return:{manager.profile.name},{manager.profile.desc},{id(manager)}"  # noqa
            )
            return manager
        elif TeamMode.NATIVE_APP == team_mode:
            raise ValueError("Native APP chat not supported!")
        else:
            raise ValueError(f"Unknown Agent Team Mode!{team_mode}")

    async def _build_employees(
        self,
        context: AgentContext,
        agent_memory: AgentMemory,
        rm: ResourceManager,
        app_details: List[GptsAppDetail],
    ) -> List[ConversableAgent]:
        """Constructing dialogue members through gpts-related Agent or gpts app information."""  # noqa
        logger.info(
            f"_build_employees:{[item.agent_role + ',' + item.agent_name for item in app_details] if app_details else ''}"  # noqa:E501
        )
        employees: List[ConversableAgent] = []
        prompt_service: PromptService = get_service()
        for record in app_details:
            logger.info(f"_build_employees循环:{record.agent_role},{record.agent_name}")
            if record.type == "app":
                gpt_app: GptsApp = deepcopy(self.gpts_app.app_detail(record.agent_role))
                if not gpt_app:
                    raise ValueError(f"Not found app {record.agent_role}!")
                employee_agent = await self._build_agent_by_gpts(
                    context, agent_memory, rm, gpt_app
                )
                logger.info(
                    f"append employee_agent:{employee_agent.profile.name},{employee_agent.profile.desc},{id(employee_agent)}"  # noqa:E501
                )
                employees.append(employee_agent)
            else:
                cls: Type[ConversableAgent] = self.agent_manage.get_by_name(
                    record.agent_role
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
                depend_resource = await blocking_func_to_async(
                    CFG.SYSTEM_APP, rm.build_resource, record.resources
                )
                agent = (
                    await cls()
                    .bind(context)
                    .bind(agent_memory)
                    .bind(llm_config)
                    .bind(depend_resource)
                    .bind(prompt_template)
                    .build()
                )
                if record.agent_describe:
                    temp_profile = agent.profile.copy()
                    temp_profile.desc = record.agent_describe
                    temp_profile.name = record.agent_name
                    agent.bind(temp_profile)
                employees.append(agent)
        logger.info(
            f"_build_employees return:{[item.profile.name if item.profile.name else '' + ',' + str(id(item)) for item in employees]}"  # noqa:E501
        )
        return employees

    async def agent_team_chat_new(
        self,
        user_query: str,
        conv_uid: str,
        conv_session_id: str,
        gpts_app: GptsApp,
        agent_memory: AgentMemory,
        is_retry_chat: bool = False,
        last_speaker_name: str = None,
        init_message_rounds: int = 0,
        link_sender: ConversableAgent = None,
        app_link_start: bool = False,
        enable_verbose: bool = True,
        historical_dialogues: Optional[List[GptsMessage]] = None,
        rely_messages: Optional[List[GptsMessage]] = None,
        **ext_info,
    ):
        gpts_status = Status.COMPLETE.value
        try:
            self.agent_manage = get_agent_manager()

            context: AgentContext = AgentContext(
                conv_id=conv_uid,
                conv_session_id=conv_session_id,
                gpts_app_code=gpts_app.app_code,
                gpts_app_name=gpts_app.app_name,
                language=gpts_app.language,
                app_link_start=app_link_start,
                enable_vis_message=enable_verbose,
            )

            rm = get_resource_manager()

            # init llm provider
            ### init chat param
            worker_manager = CFG.SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
            self.llm_provider = DefaultLLMClient(
                worker_manager, auto_convert_message=True
            )

            recipient = await self._build_agent_by_gpts(
                context, agent_memory, rm, gpts_app
            )

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
                    historical_dialogues=user_proxy.convert_to_agent_message(
                        historical_dialogues
                    ),
                    rely_messages=rely_messages,
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
            raise ValueError(f"The conversation is abnormal!{str(e)}")
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
        return await self.memory.vis_final(conv_id)

    def gpts_conv_list(self, user_code: str = None, system_app: str = None):
        return self.gpts_conversations.get_convs(user_code, system_app)

    async def topic_terminate(
        self,
        conv_id: str,
    ):
        gpts_conversations: List[GptsConversationsEntity] = (
            self.gpts_conversations.get_like_conv_id_asc(conv_id)
        )
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


def _format_vis_msg(msg: str):
    content = json.dumps({"vis": msg}, default=serialize, ensure_ascii=False)
    return f"data:{content} \n\n"


multi_agents = MultiAgents(system_app)
