import json
import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.agent import ActionOutput, AgentResource, Resource, ResourceType
from dbgpt.vis import Vis

from ...core.schema import Status
from ...resource import BaseTool, ResourcePack, ToolPack
from .tool_action import ToolAction

logger = logging.getLogger(__name__)


class AgenticRAGState(Enum):
    """Enum for Deep Search Action states."""

    REFLECTION = "reflection"
    FINAL_SUMMARIZE = "final_summarize"


class AgenticRAGModel(BaseModel):
    """Model for AgenticRAG."""

    knowledge: Optional[List[str]] = Field(
        None,
        description="List of knowledge IDs to be used in the action.",
    )
    tools: Optional[List[dict]] = Field(
        None,
        description="List of tools to be used in the action, each tool is a dict with 'tool' and 'args'.",
    )

    def to_dict(self):
        """Convert to dict."""
        return model_to_dict(self)


class AgenticRAGAction(ToolAction):
    """React action class."""

    def __init__(self, **kwargs):
        """Tool action init."""
        # self.state = "split_query"
        super().__init__(**kwargs)

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return None

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        out_put_schema = {
            "tools": [
                {
                    "tool": "工具的名称,可以是知识检索工具或搜索工具。",
                    "args": {"arg_name1": "arg_value1", "arg_name2": "arg_value2"},
                }
            ],
            "knowledge": ["knowledge_id1", "knowledge_id2"],
        }

        return f"""Please response in the following json format:
        {json.dumps(out_put_schema, indent=2, ensure_ascii=False)}
        Make sure the response is correct json and can be parsed by Python json.loads.
        """

    @classmethod
    def parse_action(
        cls,
        ai_message: str,
        default_action: "AgenticRAG",
        resource: Optional[Resource] = None,
        **kwargs,
    ) -> Optional["AgenticRAG"]:
        """Parse the action from the message.

        If you want skip the action, return None.
        """
        return default_action

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        current_goal: Optional[str] = None,
        state: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
        try:
            if state == AgenticRAGState.FINAL_SUMMARIZE.value:
                return ActionOutput(
                    is_exe_success=True,
                    content=ai_message,
                    view=ai_message,
                    terminate=True,
                )
            action_param: AgenticRAGModel = self._input_convert(
                ai_message, AgenticRAGModel
            )
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )

        if not action_param.tools and not action_param.knowledge:
            return ActionOutput(
                is_exe_success=False,
                content="No tools available for knowledge search.",
            )
        content = ""
        if action_param.knowledge:
            knowledge_ids = action_param.knowledge
            knowledge = await self.knowledge_retrieve(
                query=current_goal,
                knowledge_args=knowledge_ids,
                resource=self.resource,
            )
            content += knowledge
        if action_param.tools:
            for tool in action_param.tools:
                tool_result = await self.run_tool(
                    name=tool["tool"],
                    args=tool["args"],
                    resource=self.resource,
                    say_to_user=None,
                    render_protocol=self.render_protocol,
                    need_vis_render=need_vis_render,
                )
                content += tool_result

        return ActionOutput(
            is_exe_success=True,
            content=content,
            view=content,
            terminate=False,
            observations=content,
            state=AgenticRAGState.FINAL_SUMMARIZE.value,
        )

    async def knowledge_retrieve(
        self, query: str, knowledge_args: List[str], resource: Resource
    ) -> str:
        """Perform knowledge retrieval."""
        from dbgpt_serve.agent.resource.knowledge_pack import (
            KnowledgePackSearchResource,
        )

        knowledge_resource: KnowledgePackSearchResource = None
        if isinstance(self.resource, ResourcePack):
            for resource in self.resource.sub_resources:
                if isinstance(resource, KnowledgePackSearchResource):
                    knowledge_resource = resource
                    break
        else:
            if isinstance(resource, KnowledgePackSearchResource):
                knowledge_resource = resource
        if knowledge_resource:
            search_res = await knowledge_resource.get_summary(
                query=query, selected_knowledge_ids=knowledge_args
            )
            return search_res.summary_content
        return ""

    async def run_tool(
        self,
        name: str,
        args: dict,
        resource: Resource,
        say_to_user: Optional[str] = None,
        render_protocol: Optional[Vis] = None,
        need_vis_render: bool = False,
        raw_tool_input: Optional[str] = None,
        message_id: Optional[str] = None,
    ) -> str:
        """Run the tool."""
        is_terminal = None
        try:
            tool_packs = ToolPack.from_resource(resource)
            if not tool_packs:
                raise ValueError("The tool resource is not found！")
            tool_pack: ToolPack = tool_packs[0]

            tool_info: BaseTool = await tool_pack.get_resources_info(resource_name=name)
            logger.info(tool_info)

            response_success = True
            err_msg = None

            if raw_tool_input and tool_pack.parse_execute_args(
                resource_name=name, input_str=raw_tool_input
            ):
                parsed_args = tool_pack.parse_execute_args(
                    resource_name=name, input_str=raw_tool_input
                )
                if parsed_args and isinstance(parsed_args, tuple):
                    args = parsed_args[1]

            start_time = datetime.now().timestamp()
            try:
                tool_result = await tool_pack.async_execute(resource_name=name, **args)
                status = Status.COMPLETE.value
                is_terminal = tool_pack.is_terminal(name)
            except Exception as e:
                response_success = False
                logger.exception(f"Tool [{name}] execute failed!")
                status = Status.FAILED.value
                err_msg = f"Tool [{tool_pack.name}:{name}] execute failed! {str(e)}"
                tool_result = err_msg
        except Exception as e:
            logger.exception(f"Tool [{name}] run failed!")
            status = Status.FAILED.value
            err_msg = f"Tool [{name}] run failed! {str(e)}"
            tool_result = err_msg
        return str(tool_result)
