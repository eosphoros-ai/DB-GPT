import json
import logging
from enum import Enum
from typing import Dict, List, Optional, Union

from dbgpt.agent import ActionOutput
from dbgpt.agent.core.memory.gpts import GptsMessage, GptsPlan
from dbgpt.agent.core.schema import Status
from dbgpt.vis.vis_converter import SystemVisTag, VisProtocolConverter

from .tags.vis_app_link import VisAppLink

NONE_GOAL_PREFIX: str = "none_goal_count_"
logger = logging.getLogger(__name__)


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


class GptVisConverterNew(VisProtocolConverter):
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
        messages: List["GptsMessage"],
        plans: Optional[List["GptsPlan"]] = None,
        gpt_msg: Optional["GptsMessage"] = None,
        stream_msg: Optional[Union[Dict, str]] = None,
        is_first_chunk: bool = False,
        incremental: bool = False,
    ):
        message_view = await self.app_link_chat_message(messages)
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

    async def app_link_chat_message(self, messages: list):
        """Get app link chat message."""

        # VIS消息组装
        temp_group: Dict = {}
        app_link_message: Optional[GptsMessage] = None
        app_lanucher_message: Optional[GptsMessage] = None

        none_goal_count = 1
        for message in messages:
            if message.sender in [
                "Intent Recognition Expert",
                "App Link",
            ] or message.receiver in ["Intent Recognition Expert", "App Link"]:
                if (
                    message.sender in ["Intent Recognition Expert", "App Link"]
                    and message.receiver == "AppLauncher"
                ):
                    app_link_message = message
                if message.receiver != "Human":
                    continue

            if message.sender == "AppLauncher":
                if message.receiver == "Human":
                    app_lanucher_message = message
                continue

            current_gogal = message.current_goal

            last_goal = next(reversed(temp_group)) if temp_group else None
            if last_goal:
                last_goal_messages = temp_group[last_goal]
                if current_gogal:
                    if current_gogal == last_goal:
                        last_goal_messages.append(message)
                    else:
                        temp_group[current_gogal] = [message]
                else:
                    temp_group[f"{NONE_GOAL_PREFIX}{none_goal_count}"] = [message]
                    none_goal_count += 1
            else:
                if current_gogal:
                    temp_group[current_gogal] = [message]
                else:
                    temp_group[f"{NONE_GOAL_PREFIX}{none_goal_count}"] = [message]
                    none_goal_count += 1

        vis_items: list = []
        if app_link_message:
            vis_items.append(
                await self._messages_to_app_link_vis(
                    app_link_message, app_lanucher_message
                )
            )

        return await self._message_group_vis_build(temp_group, vis_items)

    async def _messages_to_agents_vis(
        self, messages: List[GptsMessage], is_last_message: bool = False
    ):
        if messages is None or len(messages) <= 0:
            return ""
        messages_view = []
        for message in messages:
            action_report_str = message.action_report
            view_info = message.content
            if action_report_str and len(action_report_str) > 0:
                action_out = ActionOutput.from_dict(json.loads(action_report_str))
                if action_out is not None:  # noqa
                    if action_out.is_exe_success or is_last_message:  # noqa
                        view = action_out.view
                        view_info = view if view else action_out.content

            messages_view.append(
                {
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "model": message.model_name,
                    "markdown": view_info,
                    "resource": (
                        message.resource_info if message.resource_info else None
                    ),
                }
            )
        vis_msg = self.vis_inst(SystemVisTag.VisMessage.value)
        return vis_msg.sync_display(content=messages_view)

    async def _messages_to_plan_vis(self, messages: List[Dict]):
        if messages is None or len(messages) <= 0:
            return ""
        vis_msg = self.vis_inst(SystemVisTag.VisPlans.value)
        return vis_msg.sync_display(content=messages)

    async def _messages_to_app_link_vis(
        self, link_message: GptsMessage, lanucher_message: Optional[GptsMessage] = None
    ):
        logger.info("app link vis build")
        if link_message is None:
            return ""
        param = {}
        link_report_str = link_message.action_report
        if link_report_str and len(link_report_str) > 0:
            action_out = ActionOutput.from_dict(json.loads(link_report_str))
            if action_out is not None:
                if action_out.is_exe_success:
                    temp = json.loads(action_out.content)

                    param["app_code"] = temp["app_code"]
                    param["app_name"] = temp["app_name"]
                    param["app_desc"] = temp.get("app_desc", "")
                    param["app_logo"] = ""
                    param["status"] = Status.RUNNING.value

                else:
                    param["status"] = Status.FAILED.value
                    param["msg"] = action_out.content

        if lanucher_message:
            lanucher_report_str = lanucher_message.action_report
            if lanucher_report_str and len(lanucher_report_str) > 0:
                lanucher_action_out = ActionOutput.from_dict(
                    json.loads(lanucher_report_str)
                )
                if lanucher_action_out is not None:
                    if lanucher_action_out.is_exe_success:
                        param["status"] = Status.COMPLETE.value
                    else:
                        param["status"] = Status.FAILED.value
                        param["msg"] = lanucher_action_out.content
        else:
            param["status"] = Status.COMPLETE.value
        vis_app_link = self.vis_inst(VisAppLink.vis_tag())
        return vis_app_link.sync_display(content=param)

    async def _message_group_vis_build(self, message_group, vis_items: list):
        num: int = 0
        if message_group:
            last_goal = next(reversed(message_group))
            last_goal_message = None
            if not last_goal.startswith(NONE_GOAL_PREFIX):
                last_goal_messages = message_group[last_goal]
                last_goal_message = last_goal_messages[-1]

            plan_temps: List[dict] = []
            need_show_singe_last_message = False
            for key, value in message_group.items():
                num = num + 1
                if key.startswith(NONE_GOAL_PREFIX):
                    vis_items.append(await self._messages_to_plan_vis(plan_temps))
                    plan_temps = []
                    num = 0
                    vis_items.append(await self._messages_to_agents_vis(value))
                else:
                    num += 1
                    plan_temps.append(
                        {
                            "name": key,
                            "num": num,
                            "status": "complete",
                            "agent": value[0].receiver if value else "",
                            "markdown": await self._messages_to_agents_vis(value),
                        }
                    )
                    need_show_singe_last_message = True

            if len(plan_temps) > 0:
                vis_items.append(await self._messages_to_plan_vis(plan_temps))
            if need_show_singe_last_message and last_goal_message:
                vis_items.append(
                    await self._messages_to_agents_vis([last_goal_message], True)
                )
        return "\n".join(vis_items)
