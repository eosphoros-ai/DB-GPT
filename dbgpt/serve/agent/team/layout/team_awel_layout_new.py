import json
import logging
from typing import Any, List, Optional

from pydantic import BaseModel, Field, validator

from dbgpt._private.config import Config
from dbgpt.agent.actions.action import ActionOutput, T
from dbgpt.agent.agents.agent import Agent, AgentContext, AgentGenerateContext
from dbgpt.agent.agents.base_agent_new import ConversableAgent
from dbgpt.agent.agents.base_team import ManagerAgent
from dbgpt.core.awel import DAG
from dbgpt.core.awel.dag.dag_manager import DAGManager
from dbgpt.serve.agent.team.layout.agent_operator import AwelAgentOperator

logger = logging.getLogger(__name__)

CFG = Config()


class AwelLayoutChatNewManager(ManagerAgent):
    dag: str = Field(...)
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

    async def a_act(
        self,
        message: Optional[str],
        sender: Optional[ConversableAgent] = None,
        reviewer: Optional[ConversableAgent] = None,
    ) -> Optional[ActionOutput]:
        try:
            _dag_manager = DAGManager.get_instance(CFG.SYSTEM_APP)

            dag_id = None
            try:
                dag_param = json.loads(dag)
                dag_id = dag_param["dag_id"]
            except Exception as e:
                logger.warning(f"Is not a json dag context!{dag}")
                dag_id = dag

            agent_dag = _dag_manager.dag_map[dag_id]
            last_node: AwelAgentOperator = agent_dag.leaf_nodes[0]

            start_message_context: AgentGenerateContext = AgentGenerateContext(
                message={
                    "content": message,
                    "current_gogal": message,
                },
                sender=self,
                reviewer=reviewer,
                memory=self.memory,
                agent_context=self.agent_context,
                resource_loader=self.resource_loader,
            )
            final_generate_context: AgentGenerateContext = await last_node.call(
                call_data=start_message_context
            )
            last_message = final_generate_context.rely_messages[-1]

            last_agent = await last_node.get_agent(final_generate_context)
            await last_agent.a_send(
                last_message, self, start_message_context.reviewer, False
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
