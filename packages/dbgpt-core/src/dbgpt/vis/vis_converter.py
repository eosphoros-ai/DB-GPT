from __future__ import annotations

import json
from abc import ABC
from collections import defaultdict
from enum import Enum
from importlib import util
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Type, Union

from dbgpt.vis import Vis

from ..agent.core.memory.gpts import GptsMessage, GptsPlan


def scan_vis_tags(vis_tag_paths: List[str]):
    """
    Scan the component path address specified in the current component package.
    Args:
        path: The component path address of the current component package
    Returns:

    """
    from dbgpt.util.module_utils import ModelScanner, ScannerConfig

    from .base import Vis

    scanner = ModelScanner[Vis]()
    for path in vis_tag_paths:
        config = ScannerConfig(
            module_path=path,
            base_class=Vis,
            recursive=True,
        )
        scanner.scan_and_register(config)
    return scanner.get_registered_items()


class SystemVisTag(Enum):
    """System Vis Tags."""

    VisMessage = "vis-message"
    VisPlans = "vis-plans"
    VisText = "vis-text"
    VisThinking = "vis-thinking"
    VisChart = "vis-chart"
    VisCode = "vis-code"
    VisTool = "vis-tool"
    VisTools = "vis-tools"
    VisDashboard = "vis-dashboard"
    VisSelect = "vis-select"
    VisRefs = "vis-refs"


class VisProtocolConverter(ABC):
    # The default Vis component that needs to exist as the basis for organizing message structures can be overridden.    # noqa: E501
    # If not overridden, the default component will be used
    SYSTEM_TAGS = [member.value for member in SystemVisTag]

    def __init__(self, paths: Optional[List[str]] = None):
        """Create a new AgentManager."""
        self._owned_vis_tag: Dict[str, Tuple[Type[Vis], Vis]] = defaultdict()
        self._paths = paths or [""]  # TODO 取当前路径的.tags
        if paths:
            owned_tags = scan_vis_tags(self._paths)
            for _, tag in owned_tags.items():
                self.register_vis_tag(tag)

    def system_vis_tag_map(self):
        return {
            SystemVisTag.VisMessage.value: SystemVisTag.VisMessage.value,
            SystemVisTag.VisPlans.value: SystemVisTag.VisPlans.value,
            SystemVisTag.VisText.value: SystemVisTag.VisText.value,
            SystemVisTag.VisThinking.value: SystemVisTag.VisThinking.value,
            SystemVisTag.VisChart.value: SystemVisTag.VisChart.value,
            SystemVisTag.VisCode.value: SystemVisTag.VisCode.value,
            SystemVisTag.VisTool.value: SystemVisTag.VisTool.value,
            SystemVisTag.VisTools.value: SystemVisTag.VisTools.value,
            SystemVisTag.VisDashboard.value: SystemVisTag.VisDashboard.value,
            SystemVisTag.VisRefs.value: SystemVisTag.VisRefs.value,
        }

    def vis(self, vis_tag):
        ## check if a system vis tag
        tag_name = vis_tag
        if vis_tag in self.system_vis_tag_map():
            tag_name = self.system_vis_tag_map()[vis_tag]
        if tag_name in self._owned_vis_tag:
            vis_cls, vis_inst = self._owned_vis_tag[tag_name]
            return vis_cls
        else:
            return None

    def vis_inst(self, vis_tag):
        ## check if a system vis tag
        tag_name = vis_tag
        if vis_tag in self.system_vis_tag_map():
            tag_name = self.system_vis_tag_map()[vis_tag]
        if tag_name in self._owned_vis_tag:
            vis_cls, vis_inst = self._owned_vis_tag[tag_name]
            return vis_inst
        else:
            return None

    def tag_config(self) -> dict:
        return None

    def register_vis_tag(self, cls: Type[Vis], ignore_duplicate: bool = False) -> str:
        """Register an vis tag."""
        tag_config = self.tag_config()
        inst = cls(**tag_config) if tag_config else cls()
        tag_name = inst.vis_tag()
        if tag_name in self._owned_vis_tag and (
            tag_name in self._owned_vis_tag or not ignore_duplicate
        ):
            raise ValueError(f"Vis:{tag_name} already register!")
        self._owned_vis_tag[tag_name] = (cls, inst)
        return tag_name

    async def visualization(
        self,
        messages: List[GptsMessage],
        plans: Optional[List["GptsPlan"]] = None,
        gpt_msg: Optional["GptsMessage"] = None,
        stream_msg: Optional[Union[Dict, str]] = None,
        is_first_chunk: bool = False,
        incremental: bool = False,
    ):
        pass

    async def final_view(
        self,
        messages: List["GptsMessage"],
        plans: Optional[List["GptsPlan"]] = None,
    ):
        return await self.visualization(messages, plans)

    def get_package_path_dynamic(self) -> str:
        """动态解析模块的包路径"""
        spec = util.find_spec(__name__)
        if spec and spec.parent:
            return str(Path(spec.origin).parent)
        return str(Path(__file__).parent)


class DefaultVisConverter(VisProtocolConverter):
    """None Vis Render， Just retrun message info"""

    async def visualization(
        self,
        messages: List["GptsMessage"],
        plans: Optional[List["GptsPlan"]] = None,
        gpt_msg: Optional["GptsMessage"] = None,
        stream_msg: Optional[Union[Dict, str]] = None,
        is_first_chunk: bool = False,
        incremental: bool = False,
    ):
        from dbgpt.agent import ActionOutput

        simple_message_list = []
        for message in messages:
            if message.sender == "Human":
                continue

            action_report_str = message.action_report
            view_info = message.content
            action_out = None
            if action_report_str and len(action_report_str) > 0:
                action_out = ActionOutput.from_dict(json.loads(action_report_str))
            if action_out is not None:
                view_info = action_out.content

            simple_message_list.append(
                {
                    "sender": message.sender,
                    "receiver": message.receiver,
                    "model": message.model_name,
                    "markdown": view_info,
                }
            )
        if stream_msg:
            simple_message_list.append(self._view_stream_message(stream_msg))

        return simple_message_list

    async def _view_stream_message(self, message: Dict):
        """Get agent stream message."""
        messages_view = []
        messages_view.append(
            {
                "sender": message["sender"],
                "receiver": message["receiver"],
                "model": message["model"],
                "markdown": message["markdown"],
            }
        )

        return messages_view
