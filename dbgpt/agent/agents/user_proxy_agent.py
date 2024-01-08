from typing import Callable, Dict, List, Literal, Optional, Tuple, Union

from ..memory.gpts_memory import GptsMemory
from .agent import Agent, AgentContext
from .base_agent import ConversableAgent


class UserProxyAgent(ConversableAgent):
    """(In preview) A proxy agent for the user, that can execute code and provide feedback to the other agents."""

    NAME = "User"
    DEFAULT_DESCRIBE = (
        "A human admin. Interact with the planner to discuss the plan. Plan execution needs to be approved by this admin.",
    )

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "ALWAYS",
        default_auto_reply: Optional[Union[str, Dict, None]] = "",
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=self.DEFAULT_DESCRIBE,
            system_message=self.DEFAULT_DESCRIBE,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
        )
        self.register_reply(Agent, UserProxyAgent.check_termination_and_human_reply)

    def get_human_input(self, prompt: str) -> str:
        """Get human input.

        Override this method to customize the way to get human input.

        Args:
            prompt (str): prompt for the human input.

        Returns:
            str: human input.
        """
        reply = input(prompt)
        return reply

    async def a_reasoning_reply(
        self, messages: Optional[List[Dict]] = None
    ) -> Union[str, Dict, None]:
        if messages is None or len(messages) <= 0:
            message = None
            return None, None
        else:
            message = messages[-1]
            self.plan_chat.messages.append(message)
            return message["content"], None

    async def a_receive(
        self,
        message: Optional[Dict],
        sender: Agent,
        reviewer: Agent,
        request_reply: Optional[bool] = True,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
    ):
        self.consecutive_auto_reply_counter = sender.consecutive_auto_reply_counter + 1
        self._process_received_message(message, sender, silent)

    async def check_termination_and_human_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Agent = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        """Check if the conversation should be terminated, and if human reply is provided."""
        return True, None
