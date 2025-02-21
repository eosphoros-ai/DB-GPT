"""A proxy agent for the user."""

from typing import List, Optional

from .. import ActionOutput, Agent, AgentMessage
from .base_agent import ConversableAgent
from .profile import ProfileConfig


class UserProxyAgent(ConversableAgent):
    """A proxy agent for the user.

    That can execute code and provide feedback to the other agents.
    """

    profile: ProfileConfig = ProfileConfig(
        name="User",
        role="Human",
        description=(
            "A human admin. Interact with the planner to discuss the plan. "
            "Plan execution needs to be approved by this admin."
        ),
    )

    is_human: bool = True

    ask_user: bool = False

    def have_ask_user(self):
        """If have ask user info in message."""
        return self.ask_user

    async def receive(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> None:
        """Receive a message from another agent."""
        if not silent:
            await self._a_process_received_message(message, sender)

        if message.action_report:
            action_report: ActionOutput = message.action_report
            if action_report.ask_user:
                self.ask_user = True
