import json
import logging
import uuid
from typing import List, Optional

import lyricore as lc
from fastapi import APIRouter

from dbgpt._private.config import Config
from dbgpt.agent import (
    AgentContext,
    AgentMemory,
    LLMConfig,
    UserProxyAgent,
    get_agent_manager,
)
from dbgpt.agent.core.actor_agent import AgentActorMonitor
from dbgpt.agent.core.memory.gpts import GptsMessage
from dbgpt.agent.core.schema import Status
from dbgpt.agent.util.llm.llm import LLMStrategyType
from dbgpt.core import LLMClient
from dbgpt.util.tracer.tracer_impl import root_tracer
from dbgpt_serve.agent.db import GptsConversationsDao
from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceRetrieverResource

CFG = Config()

router = APIRouter()
logger = logging.getLogger(__name__)


class DBAnalyzerController:
    def __init__(self):
        self.agent_manage = None

    async def ai_analyze_chat(
        self,
        user_query: str,
        conv_session_id: str,
        conv_uid: str,
        agent_memory: AgentMemory,
        to_free_resources: List[lc.ActorRef],
        gpts_conversations: GptsConversationsDao,
        llm_client: LLMClient,
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

            prefer_model = ext_info.get("model_name")
            available_models = await llm_client.models()
            if prefer_model:
                avaliable_reasoning_llms = [
                    m.model for m in available_models if m.model == prefer_model
                ]
            else:
                avaliable_reasoning_llms = [available_models[0].model]
            employees = []
            thinking_llm_config = LLMConfig(
                llm_client=llm_client,
                llm_strategy=LLMStrategyType.Priority,
                strategy_context=json.dumps(avaliable_reasoning_llms),
            )
            from .data_agent import DBAnalyzerManager

            data_agent_manager_ref = await lc.spawn(
                DBAnalyzerManager,
                f"_data_agent_manager_{DBAnalyzerManager.curr_cls_name()}_{conv_uid}",
                agent_context=context,
                llm_config=thinking_llm_config,
                memory=agent_memory,
            )
            to_free_resources.append(data_agent_manager_ref)
            data_agent_manager = await data_agent_manager_ref.self_proxy(with_ref=False)
            data_agent_manager.actor_ref = data_agent_manager_ref

            from .data_planning_agent import DataPlanningAgent

            planner_ref = await lc.spawn(
                DataPlanningAgent,
                f"_planner_agent_{DataPlanningAgent.curr_cls_name()}_{conv_uid}",
                agent_context=context,
                llm_config=thinking_llm_config,
                memory=agent_memory,
            )
            to_free_resources.append(planner_ref)
            planner = await planner_ref.self_proxy(with_ref=False)
            planner.actor_ref = planner_ref
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

            knowledge_agent_ref = await lc.spawn(
                KnowledgeAgent,
                f"_knowledge_agent_{KnowledgeAgent.curr_cls_name()}_{conv_uid}",
                agent_context=context,
                llm_config=thinking_llm_config,
                memory=agent_memory,
                resource=knowledge_resource,
            )
            to_free_resources.append(knowledge_agent_ref)
            knowledge_agent = await knowledge_agent_ref.self_proxy(with_ref=False)
            knowledge_agent.actor_ref = knowledge_agent_ref
            employees.append(knowledge_agent)

            # build data analysis agent
            from dbgpt.agent.expand.data_scientist_agent import DataScientistAgent

            def resource_factory():
                # Build a temporary SQLite database as an example
                from dbgpt.agent.resource import RDBMSConnectorResource
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
                db_resource = RDBMSConnectorResource(
                    "user_manager", connector=connector
                )
                return db_resource

            db_analysis_agent_ref = await lc.spawn(
                DataScientistAgent,
                f"_data_scientist_agent_{DataScientistAgent.curr_cls_name()}_{conv_uid}",
                agent_context=context,
                llm_config=thinking_llm_config,
                memory=agent_memory,
                # resource=db_resource
                # Pass a factory function to create a new resource instance avoiding
                # the db_resource cannot be serialized error
                resource_factory=resource_factory,
            )
            to_free_resources.append(db_analysis_agent_ref)
            db_analysis_agent = await db_analysis_agent_ref.self_proxy(with_ref=False)
            db_analysis_agent.actor_ref = db_analysis_agent_ref
            employees.append(db_analysis_agent)

            await data_agent_manager_ref.hire.ask(employees)

            try:
                user_proxy = await lc.actor_of(f"/user/user_proxy_actor_{conv_uid}")
                await user_proxy.stop()
            except Exception:
                pass

            user_proxy = await lc.spawn(
                UserProxyAgent,
                f"user_proxy_actor_{conv_uid}",
                agent_context=context,
                memory=agent_memory,
            )
            monitor_ref = await lc.spawn(
                AgentActorMonitor,
                f"agent_actor_monitor_{conv_uid}",
                gpts_memory=agent_memory.gpts_memory,
            )
            to_free_resources.append(monitor_ref)
            to_free_resources.append(user_proxy)
            await data_agent_manager.subscribe(monitor_ref)

            await user_proxy.initiate_chat(
                recipient=data_agent_manager,
                message=user_query,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
                message_rounds=init_message_rounds,
                historical_dialogues=UserProxyAgent.convert_to_agent_message(
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
                # await agent_memory.gpts_memory.complete(conv_uid)
                pass

        return conv_uid


db_analyzer_controller = DBAnalyzerController()
