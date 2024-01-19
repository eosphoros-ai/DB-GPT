import logging
import sys
from typing import Any, Optional

from dbgpt.agent.agents.agent import Agent, AgentContext, AgentGenerateContext
from dbgpt.agent.agents.base_team import ManagerAgent
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.awel import DAG
from dbgpt.serve.agent.team.layout.agent_operator import AgentOperator

logger = logging.getLogger(__name__)


class AwelLayoutChatManager(ManagerAgent):
    NAME = "layout_manager"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        # unlimited consecutive auto reply by default
        max_consecutive_auto_reply: Optional[int] = sys.maxsize,
        human_input_mode: Optional[str] = "NEVER",
        describe: Optional[str] = "layout chat manager.",
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            describe=describe,
            memory=memory,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )
        # Allow async chat if initiated using a_initiate_chat
        self.register_reply(
            Agent,
            AwelLayoutChatManager.a_run_chat,
        )

    async def a_run_chat(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Agent = None,
        config: Optional[Any] = None,
    ):
        try:
            last_node: AgentOperator = None
            with DAG(
                f"layout_agents_{self.agent_context.gpts_name}_{self.agent_context.conv_id}"
            ) as dag:
                for agent in self.agents:
                    now_node = AgentOperator(agent=agent)
                    if not last_node:
                        last_node = now_node
                    else:
                        last_node >> now_node
                        last_node = now_node

            start_message = {
                "content": message,
                "current_gogal": message,
            }
            start_message_context: AgentGenerateContext = AgentGenerateContext(
                message=start_message, sender=self, reviewer=reviewer
            )
            final_generate_context: AgentGenerateContext = await last_node.call(
                call_data={"data": start_message_context}
            )
            last_message = final_generate_context.rely_messages[-1]

            last_agent = last_node.agent
            await last_agent.a_send(
                last_message, self, start_message_context.reviewer, False
            )

            return True, {
                "is_exe_success": True,
                "content": last_message.get("content", None),
                "view": last_message.get("view", None),
            }
        except Exception as e:
            logger.exception("DAG run failed!")
            return True, {
                "content": f"Failed to complete goal! {str(e)}",
                "is_exe_success": False,
            }
