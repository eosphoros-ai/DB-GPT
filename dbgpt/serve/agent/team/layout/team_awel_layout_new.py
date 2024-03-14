import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from dbgpt._private.config import Config
from dbgpt.agent.actions.action import ActionOutput, T
from dbgpt.agent.agents.agent_new import Agent, AgentContext, AgentGenerateContext
from dbgpt.agent.agents.base_agent_new import ConversableAgent
from dbgpt.agent.agents.base_team import ManagerAgent
from dbgpt.core.awel import DAG
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.serve.agent.model import AwelTeamContext
from dbgpt.serve.agent.team.layout.agent_operator import AwelAgentOperator
from dbgpt.serve.flow.api.endpoints import get_service as get_flow_service
from dbgpt.serve.flow.service.service import Service as FlowService

logger = logging.getLogger(__name__)

CFG = Config()


class AwelLayoutChatNewManager(ManagerAgent):
    dag: AwelTeamContext = Field(...)
    profile: str = "AwelNewManager"
    goal: str = (
        "Promote and solve user problems according to the process arranged by Awel."
    )
    constraints: List[str] = []
    desc: str = goal

    @validator("dag")
    def check_dag(cls, value):
        assert value is not None and value != "", "dag must not be empty"
        return value

    async def _a_process_received_message(self, message: Optional[Dict], sender: Agent):
        pass

    async def a_act(
        self,
        message: Optional[str],
        sender: Optional[ConversableAgent] = None,
        reviewer: Optional[ConversableAgent] = None,
    ) -> Optional[ActionOutput]:
        try:
            flow_service: FlowService = get_flow_service()
            flow = flow_service.get({"uid": self.dag.uid})
            _dag_manager = DAGManager.get_instance(CFG.SYSTEM_APP)

            dag_id = flow.dag_id

            agent_dag = _dag_manager.dag_map[dag_id]
            if agent_dag is None:
                raise ValueError(
                    f"The configured flow cannot be found![{self.dag.name}]"
                )
            last_node: AwelAgentOperator = agent_dag.leaf_nodes[0]

            start_message_context: AgentGenerateContext = AgentGenerateContext(
                message={
                    "content": message,
                    "current_goal": message,
                },
                sender=sender,
                reviewer=reviewer,
                memory=self.memory,
                agent_context=self.agent_context,
                resource_loader=self.resource_loader,
                llm_client=self.llm_config.llm_client,
            )
            final_generate_context: AgentGenerateContext = await last_node.call(
                call_data=start_message_context
            )
            last_message = final_generate_context.rely_messages[-1]

            last_agent = await last_node.get_agent(final_generate_context)
            last_agent.consecutive_auto_reply_counter = (
                final_generate_context.round_index
            )
            await last_agent.a_send(
                last_message, sender, start_message_context.reviewer, False
            )

            return ActionOutput(
                content=last_message.get("content", None),
                view=last_message.get("view", None),
            )
        except Exception as e:
            logger.exception(f"DAG run failed!{str(e)}")

            return ActionOutput(
                is_exe_success=False,
                content=f"Failed to complete goal! {str(e)}",
            )
