import json
import logging
from enum import Enum
from typing import Dict, List, Optional, Union

from dbgpt.agent import ActionOutput, UserProxyAgent
from dbgpt.agent.core.memory.gpts import GptsMessage, GptsPlan
from dbgpt.vis.vis_converter import SystemVisTag, VisProtocolConverter

NONE_GOAL_PREFIX: str = "none_goal_count_"
logger = logging.getLogger(__name__)


def vis_name_change(vis_message: str) -> str:
    """Change vis tag name use new name."""
    replacements = {
        "```vis-chart": "```vis-db-chart",
    }

    for old_tag, new_tag in replacements.items():
        vis_message = vis_message.replace(old_tag, new_tag)

    return vis_message


class GptVisTagPackage(Enum):
    """System Vis Tags."""

    AgentMessage = "agent-messages"
    AgentPlans = "agent-plans"
    APIResponse = "vis-api-response"
    AppLink = "vis-app-link"
    Chart = "vis-db-chart"
    Code = "vis-code"
    Dashboard = "vis-dashboard"
    Flow = "agent-flow"
    Result = "agent-result"
    Plugin = "vis-plugin"
    Tools = "vis-tools"
    Thinking = "vis-thinking"
    Text = "vis-text"


class GptVisConverter(VisProtocolConverter):
    def __init__(self, paths: Optional[str] = None):
        default_tag_paths = ["dbgpt_ext.vis.gpt_vis.tags"]
        super().__init__(paths if paths else default_tag_paths)

    def system_vis_tag_map(self):
        return {
            SystemVisTag.VisMessage.value: GptVisTagPackage.AgentMessage.value,
            SystemVisTag.VisPlans.value: GptVisTagPackage.AgentPlans.value,
            SystemVisTag.VisText.value: GptVisTagPackage.Text.value,
            SystemVisTag.VisThinking.value: GptVisTagPackage.Thinking.value,
            SystemVisTag.VisChart.value: GptVisTagPackage.Chart.value,
            SystemVisTag.VisCode.value: GptVisTagPackage.Code.value,
            SystemVisTag.VisTool.value: GptVisTagPackage.Plugin.value,
            SystemVisTag.VisTools.value: GptVisTagPackage.Plugin.value,
            SystemVisTag.VisDashboard.value: GptVisTagPackage.Dashboard.value,
        }

    async def visualization_stream(self, stream_msg: Optional[Union[Dict, str]] = None):
        return await self.agent_stream_message(stream_msg)

    async def visualization(
        self,
        messages: List[GptsMessage],
        plans: Optional[List[GptsPlan]] = None,
        gpt_msg: Optional[GptsMessage] = None,
        stream_msg: Optional[Union[Dict, str]] = None,
    ):
        # VIS消息组装
        deal_messages: List[GptsMessage] = []
        for message in messages:
            if not message.action_report and message.receiver != UserProxyAgent.role:
                continue
            deal_messages.append(message)
            # last_message: Optional[GptsMessage] = (
            #     deal_messages[-1] if len(deal_messages) > 0 else None
            # )
            # if last_message and last_message.sender_name != message.sender_name:
            #     deal_messages.append(message)
            # else:
            #     ## 直接替换最后一个
            #     if len(deal_messages) > 0:
            #         deal_messages[-1] = message
            #     else:
            #         deal_messages.append(message)

        deal_messages = sorted(deal_messages, key=lambda _message: _message.rounds)
        vis_items: List[str] = []
        for message in deal_messages:
            vis_items.append(await self._messages_to_agents_vis(message))
        message_view = "\n".join(vis_items)
        if stream_msg:
            temp_view = await self.agent_stream_message(stream_msg)
            message_view = message_view + "\n" + temp_view
        return message_view

    async def agent_stream_message(
        self,
        message: Dict,
    ):
        """Get agent stream message."""
        messages_view = []
        thinking = message.get("thinking")
        markdown = message.get("content")
        vis_thinking = self.vis_inst(SystemVisTag.VisThinking.value)
        msg_markdown = ""
        if thinking:
            vis_thinking = vis_thinking.sync_display(content=thinking)
            msg_markdown = vis_thinking
        if markdown:
            msg_markdown = msg_markdown + "\n" + markdown

        messages_view.append(
            {
                "sender": message["sender"],
                "model": message["model"],
                "markdown": msg_markdown,
            }
        )

        return await self.vis_inst(SystemVisTag.VisMessage.value).display(
            content=messages_view
        )

    async def _messages_to_agents_vis(
        self, message: GptsMessage, is_last_message: bool = False
    ):
        if message is None:
            return ""
        messages_view = []

        action_report_str = message.action_report
        view_info = message.content
        if action_report_str and len(action_report_str) > 0:
            action_out = ActionOutput.from_dict(json.loads(action_report_str))
            if action_out is not None:  # noqa
                if action_out.is_exe_success or is_last_message:  # noqa
                    view = action_out.view
                    view_info = view if view else action_out.content

        thinking = message.thinking
        vis_thinking = self.vis_inst(SystemVisTag.VisThinking.value)
        if thinking:
            vis_thinking = vis_thinking.sync_display(content=thinking)
            view_info = vis_thinking + "\n" + view_info

        messages_view.append(
            {
                "sender": message.sender_name or message.sender,
                "receiver": message.receiver_name or message.receiver,
                "model": message.model_name,
                "markdown": view_info,
                "resource": (message.resource_info if message.resource_info else None),
            }
        )
        return await self.vis_inst(SystemVisTag.VisMessage.value).display(
            content=messages_view
        )
