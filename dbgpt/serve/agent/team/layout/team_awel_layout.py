import logging
from typing import Any, List, Optional

from dbgpt.agent.actions.action import ActionOutput, T
from dbgpt.agent.agents.agent import Agent, AgentContext, AgentGenerateContext
from dbgpt.agent.agents.base_agent_new import ConversableAgent
from dbgpt.agent.agents.base_team import ManagerAgent
from dbgpt.core.awel import DAG
from dbgpt.serve.agent.team.layout.agent_operator import AgentOperator

logger = logging.getLogger(__name__)


class AwelLayoutChatManager(ManagerAgent):
    profile: str = "AwelManager"
    goal: str = (
        "Promote and solve user problems according to the process arranged by Awel."
    )
    constraints: List[str] = []
    desc: str = goal

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def a_act(
        self,
        message: Optional[str],
        sender: Optional[ConversableAgent] = None,
        reviewer: Optional[ConversableAgent] = None,
    ) -> Optional[ActionOutput]:
        try:
            # TODO Use programmed DAG
            last_node: AgentOperator = None
            with DAG(
                f"layout_agents_{self.agent_context.gpts_app_name}_{self.agent_context.conv_id}"
            ) as dag:
                for agent in self.agents:
                    now_node = AgentOperator(agent=agent)
                    if not last_node:
                        last_node = now_node
                    else:
                        last_node >> now_node
                        last_node = now_node

            start_message_context: AgentGenerateContext = AgentGenerateContext(
                message={
                    "content": message,
                    "current_goal": message,
                },
                sender=self,
                reviewer=reviewer,
            )
            final_generate_context: AgentGenerateContext = await last_node.call(
                call_data=start_message_context
            )
            last_message = final_generate_context.rely_messages[-1]

            last_agent = last_node.agent
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
