from abc import ABC
from typing import Dict, List, Optional

from dbgpt.agent.agents.agent import Agent, AgentGenerateContext
from dbgpt.core.awel import BranchFunc, BranchOperator, MapOperator
from dbgpt.core.interface.message import ModelMessageRoleType


class BaseAgentOperator:
    """The abstract operator for a Agent."""

    SHARE_DATA_KEY_MODEL_NAME = "share_data_key_agent_name"

    def __init__(self, agent: Optional[Agent] = None):
        self._agent = agent

    @property
    def agent(self) -> Agent:
        """Return the Agent."""
        if not self._agent:
            raise ValueError("agent is not set")
        return self._agent


class AgentOperator(
    BaseAgentOperator, MapOperator[AgentGenerateContext, AgentGenerateContext], ABC
):
    def __init__(self, agent: Agent, **kwargs):
        super().__init__(agent=agent)
        MapOperator.__init__(self, **kwargs)

    async def map(self, input_value: AgentGenerateContext) -> AgentGenerateContext:
        now_rely_messages: List[Dict] = []

        # input_value.message["current_gogal"] = (
        #     self._agent.name + ":" + input_value.message["current_gogal"]
        # )
        ###What was received was the User message
        human_message = input_value.message.copy()
        human_message["role"] = ModelMessageRoleType.HUMAN
        now_rely_messages.append(human_message)

        ###Send a message (no reply required) and pass the message content
        now_message = input_value.message
        if input_value.rely_messages and len(input_value.rely_messages) > 0:
            now_message = input_value.rely_messages[-1]
        await input_value.sender.a_send(
            now_message, self._agent, input_value.reviewer, False
        )

        ### Retry on failure
        current_message = input_value.message
        final_sucess = False
        final_message = None
        while self.agent.current_retry_counter < self.agent.max_retry_count:
            verify_paas, reply_message = await self._agent.a_generate_reply(
                message=current_message,
                sender=input_value.sender,
                reviewer=input_value.reviewer,
                silent=input_value.silent,
                rely_messages=input_value.rely_messages,
            )
            final_message = reply_message
            if verify_paas:
                final_sucess = True
                break
            else:
                # retry
                current_message = {
                    "content": reply_message["content"],
                    "current_gogal": input_value.message.get("current_gogal", None),
                }
                await input_value.sender.a_send(
                    current_message, self.agent, input_value.reviewer, False
                )
                self.agent.current_retry_counter += 1
        if not final_sucess:
            raise ValueError(
                f"After trying {self.agent.current_retry_counter} times, I still can't generate a valid answer. The current problem is:{final_message['content']}!"
            )

        ###What is sent is an AI message
        ai_message = final_message
        ai_message["role"] = ModelMessageRoleType.AI
        now_rely_messages.append(ai_message)

        ### Handle user goals and outcome dependencies
        return AgentGenerateContext(
            message=input_value.message,
            sender=self._agent,
            reviewer=input_value.reviewer,
            rely_messages=now_rely_messages,  ## Default single step transfer of information
            silent=input_value.silent,
        )
