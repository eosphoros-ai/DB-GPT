import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, Union

from dbgpt._private.pydantic import Field
from dbgpt.agent import (
    ActionOutput,
    Agent,
    AgentMemoryFragment,
    AgentMessage,
    ConversableAgent,
    ProfileConfig,
    Resource,
    ResourceType,
    StructuredAgentMemoryFragment,
)
from dbgpt.agent.core.role import AgentRunMode
from dbgpt.agent.resource import BaseTool, ResourcePack, ToolPack
from dbgpt.agent.util.react_parser import ReActOutputParser
from dbgpt.util.configure import DynConfig
from .actions.deep_search_action import DeepSearchAction

from ...core import ModelMessageRoleType
from .actions.react_action import ReActAction, Terminate
from ...util.tracer import root_tracer

logger = logging.getLogger(__name__)

_DEEPSEARCH_GOAL = """Answer the following questions or solve the tasks by \
selecting the right search tools. 
"""

# _DEEPSEARCH_SYSTEM_TEMPLATE = """
# You are a DeepSearch Assistant. Your task is to answer questions or solve problems by utilizing a combination of knowledge retrieve tools and search tools. You should break down the task, search for information, reflect on the results, and synthesize a comprehensive answer.
#
# <AVAILABLE TOOLS>
# 1. Knowledge Tools: Query the internal knowledge base for information. \n {{knowledge_tools}}
# 2. WebSearch Tools: Perform an internet search for up-to-date or additional information. \n {{search_tools}}
# 3. Summarize: Summarize and synthesize information from multiple sources.
# </AVAILABLE TOOLS>
#
# # PROCESS #
# 1. Analyze the task and create a search plan.
# 2. Use one or more tools to gather information.
# 3. Reflect on the gathered information and determine if it's sufficient to answer the question.
# 4. If the information is insufficient, revise your plan and continue searching.
# 5. Once you have enough information, synthesize a final answer.
#
# <RESPONSE FORMAT>
# For each step in your process, your response should contain:
# 1. Analysis of the current state and reasoning for your next action (prefix "Thought: ").
# 2. One or more tool uses, each containing:
#    - Tool name (prefix "Tool: ").
#    - Tool input (prefix "Input: ").
# 3. After receiving tool output, a reflection on the information (prefix "Reflection: ").
# </RESPONSE FORMAT>
#
# <EXAMPLE>
# Human: Who won the Nobel Prize in Literature in 2022?
#
# DeepSearch:
# Thought: To answer this question, I need to search for recent information about the Nobel Prize in Literature. I'll start with a web search as it's likely to have the most up-to-date information.
#
# Tool: WebSearch
# Input: Nobel Prize in Literature 2022 winner
# </EXAMPLE>
#
# <TASK>
# Please Solve this task:
# {{ question }}
# </TASK>
#
# The current time is: {{ now_time }}.
# """
_DEEPSEARCH_SYSTEM_TEMPLATE = """
你是一个深度搜索助手。你的任务是你将用户原始问题一个或者多个子问题，并且给出可用知识库工具和搜索工具来回答问题或解决问题。

<可用工具>
1. KnowledgeRetrieve: 查询内部知识库以获取信息。\n可用知识库: {{knowledge_tools}}
2. WebSearch: 进行互联网搜索以获取最新或额外信息。\n 可用搜索工具: {{search_tools}}
3. 总结: 对多个来源的信息进行总结和综合。
</可用工具>

<流程>
1. 分析任务并创建搜索计划。
2. 选择使用一个或多个工具收集信息。
</流程>

<回复格式>
严格按以下JSON格式输出，确保可直接解析：
{
  "status": "split_query (拆解搜索计划) | summary (仅当可用知识可以回答用户问题) | reflection (反思) "
  "tools": [{
    "tool_type": "工具类型"
    "args": "args1",
  }],
  "intention": "当前你的意图,
  "sub_queries": [],
}
</回复格式>

<示例>
人类: 谁在2022年获得了诺贝尔文学奖？

深度搜索:
思考: 要回答这个问题,我需要搜索关于2022年诺贝尔文学奖的最新信息。我会从网络搜索开始,因为这可能会有最新的信息。
<可用工具>
1. KnowledgeRetrieve: 查询内部知识库以获取信息。\n可用知识库: {{knowledge_tools}}
2. WebSearch: 进行互联网搜索以获取最新或额外信息。\n 可用搜索工具: {{search_tools}}

3. 总结: 对多个来源的信息进行总结和综合。
</可用工具>
工具类型: KnowledgeRetrieve
工具参数: 
: 2022年诺贝尔文学奖得主
返回
{
  "status": "split_query"
  "tools"?: [{
    "tool_type": "KnowledgeRetrieve"
    "args": "knowledge_name",
  }],
  "intention": "你的拆解意图,
  "sub_queries": [],
}
</示例>

<任务>
请解决这个任务:
{{ question }}
</任务>

当前时间是: {{ now_time }}。
"""

_DEEPSEARCH_USER_TEMPLATE = """"""


_REACT_WRITE_MEMORY_TEMPLATE = """\
{% if question %}Question: {{ question }} {% endif %}
{% if thought %}Thought: {{ thought }} {% endif %}
{% if action %}Action: {{ action }} {% endif %}
{% if action_input %}Action Input: {{ action_input }} {% endif %}
{% if observation %}Observation: {{ observation }} {% endif %}
"""


class DeepSearchAgent(ConversableAgent):
    max_retry_count: int = 15
    run_mode: AgentRunMode = AgentRunMode.LOOP

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "DeepSearchAssistant",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_name",
        ),
        role=DynConfig(
            "DeepSearchAssistant",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_role",
        ),
        goal=DynConfig(
            _DEEPSEARCH_GOAL,
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_goal",
        ),
        system_prompt_template=_DEEPSEARCH_SYSTEM_TEMPLATE,
        user_prompt_template=_DEEPSEARCH_USER_TEMPLATE,
        write_memory_template=_REACT_WRITE_MEMORY_TEMPLATE,
    )
    parser: ReActOutputParser = Field(default_factory=ReActOutputParser)

    def __init__(self, **kwargs):
        """Init indicator AssistantAgent."""
        super().__init__(**kwargs)

        self._init_actions([DeepSearchAction, Terminate])

    # async def _a_init_reply_message(
    #     self,
    #     received_message: AgentMessage,
    #     rely_messages: Optional[List[AgentMessage]] = None,
    # ) -> AgentMessage:
    #     reply_message = super()._init_reply_message(received_message, rely_messages)
    #
    #     tool_packs = ToolPack.from_resource(self.resource)
    #     action_space = []
    #     action_space_names = []
    #     action_space_simple_desc = []
    #     if tool_packs:
    #         tool_pack = tool_packs[0]
    #         for tool in tool_pack.sub_resources:
    #             tool_desc, _ = await tool.get_prompt(lang=self.language)
    #             action_space_names.append(tool.name)
    #             action_space.append(tool_desc)
    #             if isinstance(tool, BaseTool):
    #                 tool_simple_desc = tool.description
    #             else:
    #                 tool_simple_desc = tool.get_prompt()
    #             action_space_simple_desc.append(f"{tool.name}: {tool_simple_desc}")
    #     else:
    #         for action in self.actions:
    #             action_space_names.append(action.name)
    #             action_space.append(action.get_action_description())
    #         # self.actions
    #     reply_message.context = {
    #         "max_steps": self.max_retry_count,
    #         "action_space": "\n".join(action_space),
    #         "action_space_names": ", ".join(action_space_names),
    #         "action_space_simple_desc": "\n".join(action_space_simple_desc),
    #     }
    #     return reply_message

    async def preload_resource(self) -> None:
        await super().preload_resource()
        self._check_and_add_terminate()

    async def generate_resource_variables(
        self, resource_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate the resource variables."""
        out_schema: Optional[str] = ""
        if self.actions and len(self.actions) > 0:
            out_schema = self.actions[0].ai_out_schema
        if not resource_prompt:
            resource_prompt = ""
        now_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "knowledge_tools": resource_prompt,
            "search_tools": "",
            "out_schema": out_schema,
            "now_time": now_time,
        }

    def _check_and_add_terminate(self):
        if not self.resource:
            return
        _is_has_terminal = False

        def _has_terminal(r: Resource):
            nonlocal _is_has_terminal
            if r.type() == ResourceType.Tool and isinstance(r, Terminate):
                _is_has_terminal = True
            return r

        _has_add_terminal = False

        def _add_terminate(r: Resource):
            nonlocal _has_add_terminal
            if not _has_add_terminal and isinstance(r, ResourcePack):
                terminal = Terminate()
                r._resources[terminal.name] = terminal
                _has_add_terminal = True
            return r

        self.resource.apply(apply_func=_has_terminal)
        if not _is_has_terminal:
            # Add terminal action to the resource
            self.resource.apply(apply_pack_func=_add_terminate)

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load agent bind resource."""
        abilities = []
        if self.resource:
            def _remove_tool(r: Resource):
                if r.type() == ResourceType.Tool:
                    return None
                return r

            # Remove all tools from the resource
            # We will handle tools separately

            if isinstance(self.resource, ResourcePack):
                for resource in self.resource.sub_resources:
                    from dbgpt_serve.agent.resource.knowledge import \
                        KnowledgeSpaceRetrieverResource
                    if isinstance(resource, KnowledgeSpaceRetrieverResource):
                        abilities.append({
                            "knowledge_name": resource.retriever_name,
                            "knowledge_desc": resource.retriever_desc,
                        })
            else:
                from dbgpt_serve.agent.resource.knowledge import KnowledgeSpaceRetrieverResource
                if isinstance(self.resource, KnowledgeSpaceRetrieverResource):
                    abilities.append({
                        "knowledge_name": self.resource.retriever_name,
                        "knowledge_desc": self.resource.retriever_desc,
                    })

            # new_resource = self.resource.apply(apply_func=_remove_tool)
            # if new_resource:
            #     resource_prompt, resource_reference = await new_resource.get_prompt(
            #         lang=self.language, question=question
            #     )
            #     return resource_prompt, resource_reference
        return json.dumps(abilities, ensure_ascii=False), []

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare the parameters for the act method."""
        return {
            "parser": self.parser,
        }

    async def act(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        """Perform actions."""
        last_out: Optional[ActionOutput] = None
        for i, action in enumerate(self.actions):
            if not message:
                raise ValueError("The message content is empty!")

            with root_tracer.start_span(
                "agent.act.run",
                metadata={
                    "message": message,
                    "sender": sender.name if sender else None,
                    "recipient": self.name,
                    "reviewer": reviewer.name if reviewer else None,
                    "rely_action_out": last_out.to_dict() if last_out else None,
                    "conv_uid": self.not_null_agent_context.conv_id,
                    "action_index": i,
                    "total_action": len(self.actions),
                },
            ) as span:
                ai_message = message.content if message.content else ""
                # real_action = action.parse_action(
                #     ai_message, default_action=action, **kwargs
                # )
                # if real_action is None:
                #     continue

                last_out = await action.run(
                    ai_message=message.content if message.content else "",
                    resource=None,
                    rely_action_out=last_out,
                    **kwargs,
                )
                span.metadata["action_out"] = last_out.to_dict() if last_out else None
        if not last_out:
            raise ValueError("Action should return value！")
        return last_out

    @property
    def memory_fragment_class(self) -> Type[AgentMemoryFragment]:
        """Return the memory fragment class."""
        return StructuredAgentMemoryFragment

    async def read_memories(
        self,
        observation: str,
    ) -> Union[str, List["AgentMessage"]]:
        memories = await self.memory.read(observation)
        not_json_memories = []
        messages = []
        structured_memories = []
        for m in memories:
            if m.raw_observation:
                try:
                    mem_dict = json.loads(m.raw_observation)
                    if isinstance(mem_dict, dict):
                        structured_memories.append(mem_dict)
                    elif isinstance(mem_dict, list):
                        structured_memories.extend(mem_dict)
                    else:
                        raise ValueError("Invalid memory format.")
                except Exception:
                    not_json_memories.append(m.raw_observation)

        for mem_dict in structured_memories:
            question = mem_dict.get("question")
            thought = mem_dict.get("thought")
            action = mem_dict.get("action")
            action_input = mem_dict.get("action_input")
            observation = mem_dict.get("observation")
            if question:
                messages.append(
                    AgentMessage(
                        content=f"Question: {question}",
                        role=ModelMessageRoleType.HUMAN,
                    )
                )
            ai_content = []
            if thought:
                ai_content.append(f"Thought: {thought}")
            if action:
                ai_content.append(f"Action: {action}")
            if action_input:
                ai_content.append(f"Action Input: {action_input}")
            messages.append(
                AgentMessage(
                    content="\n".join(ai_content),
                    role=ModelMessageRoleType.AI,
                )
            )

            if observation:
                messages.append(
                    AgentMessage(
                        content=f"Observation: {observation}",
                        role=ModelMessageRoleType.HUMAN,
                    )
                )

        if not messages and not_json_memories:
            messages.append(
                AgentMessage(
                    content="\n".join(not_json_memories),
                    role=ModelMessageRoleType.HUMAN,
                )
            )
        return messages
