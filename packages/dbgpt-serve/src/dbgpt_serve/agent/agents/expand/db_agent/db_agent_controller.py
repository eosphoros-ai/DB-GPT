import json
import logging
import uuid
from abc import ABC
from typing import List, Optional

from fastapi import APIRouter

from dbgpt._private.config import Config
from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    LLMConfig,
    UserProxyAgent,
    get_agent_manager,
)
from dbgpt.agent.core.base_team import ManagerAgent
from dbgpt.agent.core.memory.gpts import GptsMessage
from dbgpt.agent.core.schema import Status
from dbgpt.agent.util.llm.llm import LLMStrategyType
from dbgpt.component import ComponentType
from dbgpt.model.cluster import WorkerManagerFactory
from dbgpt.model.cluster.client import DefaultLLMClient
from dbgpt.util.tracer.tracer_impl import root_tracer
from dbgpt_serve.agent.app.gpts_server import available_llms
from dbgpt_serve.agent.db import GptsConversationsDao
from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceRetrieverResource

CFG = Config()

router = APIRouter()
logger = logging.getLogger(__name__)


class DBAnalyzerController(ABC):
    async def ai_analyze_chat(
        self,
        user_query: str,
        conv_session_id: str,
        conv_uid: str,
        agent_memory: AgentMemory,
        gpts_conversations: GptsConversationsDao,
        is_retry_chat: bool = False,
        last_speaker_name: str = None,
        init_message_rounds: int = 0,
        app_link_start: bool = False,
        historical_dialogues: Optional[List[GptsMessage]] = None,
        rely_messages: Optional[List[GptsMessage]] = None,
        stream: Optional[bool] = True,
        **ext_info,
    ):
        gpts_status = Status.COMPLETE.value
        try:
            self.agent_manage = get_agent_manager()

            context: AgentContext = AgentContext(
                conv_id=conv_uid,
                conv_session_id=conv_session_id,
                trace_id=ext_info.get("trace_id", uuid.uuid4().hex),
                rpc_id=ext_info.get("rpc_id", "0.1"),
                gpts_app_code="ai_analyzer",
                gpts_app_name="AI_ANALYZER",
                language="zh",
                app_link_start=app_link_start,
                incremental=ext_info.get("incremental", False),
                stream=stream,
            )
            root_tracer.start_span(
                operation_name="agent_chat", parent_span_id=context.trace_id
            )
            # init llm provider
            ### init chat param
            worker_manager = CFG.SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
            llm_provider = DefaultLLMClient(worker_manager, auto_convert_message=True)

            available_models = await llm_provider.models()
            avaliable_reasoning_llms = [available_models[0].model]
            employees = []
            thinking_llm_config = LLMConfig(
                llm_client=llm_provider,
                llm_strategy=LLMStrategyType.Priority,
                strategy_context=json.dumps(avaliable_reasoning_llms),
            )
            from .data_agent import DBAnalyzerManager

            data_agent_manager: ManagerAgent = (
                await DBAnalyzerManager()
                .bind(context)
                .bind(agent_memory)
                .bind(thinking_llm_config)
                .build()
            )

            from .data_planning_agent import DataPlanningAgent

            planner = (
                await DataPlanningAgent()
                .bind(context)
                .bind(agent_memory)
                .bind(thinking_llm_config)
                .build()
            )
            employees.append(planner)
            # data agent bind knowledge agent
            from dbgpt_serve.agent.agents.expand.db_agent.knowledge_agent import (
                KnowledgeAgent,
            )

            knowledge_resource = KnowledgeSpaceRetrieverResource(
                name="数据分析知识库",
                space_name="数据分析知识库",
                system_app=CFG.SYSTEM_APP,
            )
            knowledge_agent = (
                await KnowledgeAgent()
                .bind(context)
                .bind(knowledge_resource)
                .bind(agent_memory)
                .bind(thinking_llm_config)
                .build()
            )
            employees.append(knowledge_agent)

            # build data analysis agent
            from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent
            from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteTempConnector

            connector = SQLiteTempConnector.create_temporary_db()
            connector.create_temp_tables(
                {
                    "user": {
                        "columns": {
                            "id": "INTEGER PRIMARY KEY",
                            "name": "TEXT",
                            "age": "INTEGER",
                        },
                        "data": [
                            (1, "Tom", 10),
                            (2, "Jerry", 16),
                            (3, "Jack", 18),
                            (4, "Alice", 20),
                            (5, "Bob", 22),
                        ],
                    }
                }
            )
            from dbgpt.agent.resource import RDBMSConnectorResource

            db_resource = RDBMSConnectorResource("user_manager", connector=connector)
            db_analysis_agent = (
                await DataScientistAgent()
                .bind(context)
                .bind(thinking_llm_config)
                .bind(db_resource)
                .bind(agent_memory)
                .build()
            )
            employees.append(db_analysis_agent)

            data_agent_manager.hire(employees)

            user_proxy: UserProxyAgent = (
                await UserProxyAgent().bind(context).bind(agent_memory).build()
            )

            await user_proxy.initiate_chat(
                recipient=data_agent_manager,
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
                gpts_conversations.update(conv_uid, gpts_status)
        except Exception as e:
            logger.error(f"chat abnormal termination！{str(e)}", e)
            gpts_conversations.update(conv_uid, Status.FAILED.value)
            raise ValueError(f"The conversation is abnormal!{str(e)}")
        finally:
            if not app_link_start:
                await agent_memory.gpts_memory.complete(conv_uid)

        return conv_uid


db_analyzer_controller = DBAnalyzerController()
