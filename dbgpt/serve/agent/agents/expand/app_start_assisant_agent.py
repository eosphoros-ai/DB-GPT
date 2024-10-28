import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from dbgpt.agent import (
    ActionOutput,
    Agent,
    AgentMessage,
    ConversableAgent,
    get_agent_manager,
)
from dbgpt.agent.core.memory.gpts import GptsMessage
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt.serve.agent.agents.expand.actions.app_start_action import StartAppAction

logger = logging.getLogger()


class StartAppAssistantAgent(ConversableAgent):
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "AppLauncher",
            category="agent",
            key="dbgpt_ant_agent_agents_app_start_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "AppLauncher",
            category="agent",
            key="dbgpt_ant_agent_agents_app_start_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "The agent starts the selected application.",
            category="agent",
            key="dbgpt_ant_agent_agents_app_start_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [],
            category="agent",
            key="dbgpt_ant_agent_agents_app_start_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "The agent starts the selected application.",
            category="agent",
            key="dbgpt_ant_agent_agents_app_start_assistant_agent_profile_desc",
        ),
    )
    last_rounds: int = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([StartAppAction])

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> Dict[str, Any]:
        return {
            "user_input": received_message.content,
            "conv_id": self.agent_context.conv_id,
            "paren_agent": self,
        }

    async def _load_thinking_messages(
        self,
        received_message: AgentMessage,
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: Optional[bool] = False,
    ) -> tuple[List[AgentMessage], Optional[Dict]]:
        if rely_messages and len(rely_messages) > 0:
            return rely_messages[-1:], None
        else:
            raise ValueError("没有可用的应用链接消息！")

    async def thinking(
        self,
        messages: List[AgentMessage],
        sender: Optional[Agent] = None,
        prompt: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        return messages[0].action_report.content, None

    async def receive(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: str = None,
    ) -> None:
        await self._a_process_received_message(message, sender)
        if request_reply is False or request_reply is None:
            return

        if sender.agent_context.app_link_start:
            self.last_rounds = message.rounds

        elif not self.is_human and not sender.agent_context.app_link_start:
            is_success, reply = await self.generate_reply(
                received_message=message,
                sender=sender,
                reviewer=reviewer,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
            )
            if reply is not None:
                await self.a_send(reply, sender, silent=True)

    async def adjust_final_message(
        self,
        is_success: bool,
        reply_message: AgentMessage,
    ):
        if self.last_rounds > 0:
            reply_message.rounds = self.last_rounds
        return is_success, reply_message

    async def act(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        last_out = None
        for action in self.actions:
            # Select the resources required by acton
            last_out: ActionOutput = await action.run(
                ai_message=message.content,
                resource=self.resource,
                rely_action_out=last_out,
                init_message_rounds=message.rounds,
                **kwargs,
            )
            history_messages: List[
                GptsMessage
            ] = await self.memory.gpts_memory.get_messages(self.agent_context.conv_id)
            last_gpt_message = history_messages[-1]
            if history_messages:
                message.rounds = last_gpt_message.rounds

        return ActionOutput.from_dict(json.loads(last_gpt_message.action_report))


agent_manage = get_agent_manager()
agent_manage.register_agent(StartAppAssistantAgent)
