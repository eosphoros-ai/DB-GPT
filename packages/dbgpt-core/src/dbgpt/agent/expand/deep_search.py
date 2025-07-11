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
你是一个深度搜索助手。
<目标>
你的任务是根据用户的问题或任务，选择合适的知识检索工具和搜索工具来回答问题或解决问题。
你需要根据已经搜到的知识和搜索到的信息:
{{most_recent_memories}}判断是否需要更多的知识或信息来回答问题。
如果需要更多的知识或信息，你需要提出后续的子问题来扩展你的理解。
</目标>

<可用工具>
1. KnowledgeRetrieve: 查询内部知识库以获取信息。\n可用知识库: {{knowledge_tools}}
2. WebSearch: 进行互联网搜索以获取最新或额外信息。\n 可用搜索工具: {{search_tools}}
</可用工具>

<流程>
1. 分析任务并创建搜索计划。
2. 选择使用一个或多个工具收集信息。
3. 对收集到的信息进行反思，判断是否足够回答问题。
</流程>

<回复格式>
严格按以下JSON格式输出，确保可直接解析：
{
  "tools": [{
    "tool_type": "工具类型"
    "args": "args1",
  }],
  "intention": "当前你的意图,
  "sub_queries": ["子问题1", "子问题2"],
  "knowledge_gap": "总结缺乏关于性能指标和基准的信息",
  "status": "reflection(反思) | summarize(最后总结)",
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
  "status": "reflection"
  "tools"?: [{
    "tool_type": "KnowledgeRetrieve"
    "args": "knowledge_name",
  }],
  "intention": "你的拆解意图,
  "knowledge_gap": "总结缺乏关于2022年诺贝尔文学奖得主的信息",
  "sub_queries": ["子问题1","子问题2"],
}
</示例>

<任务>
请解决这个任务:
{{ question }}
</任务>

当前时间是: {{ now_time }}。
"""

_DEEPSEARCH_USER_TEMPLATE = """"""
_DEEPSEARCH_FINIAL_SUMMARY_TEMPLATE = """
<GOAL>
Generate a high-quality summary of the provided context.
</GOAL>

<REQUIREMENTS>
When creating a NEW summary:
1. Highlight the most relevant information related to the user topic from the search results
2. Ensure a coherent flow of information

When EXTENDING an existing summary:  
{{most_recent_memories}}                                                                                                               
1. Read the existing summary and new search results carefully.                                                    
2. Compare the new information with the existing summary.                                                         
3. For each piece of new information:                                                                             
    a. If it's related to existing points, integrate it into the relevant paragraph.                               
    b. If it's entirely new but relevant, add a new paragraph with a smooth transition.                            
    c. If it's not relevant to the user topic, skip it.                                                            
4. Ensure all additions are relevant to the user's topic.                                                         
5. Verify that your final output differs from the input summary.                                                                                                                                                            
< /REQUIREMENTS >

< FORMATTING >
- Start directly with the updated summary, without preamble or titles. Do not use XML tags in the output.  
< /FORMATTING >

<Task>
Think carefully about the provided Context first. Then generate a summary of the context to address the User Input.
</Task>
"""


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

        self._init_actions([DeepSearchAction])

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

        return json.dumps(abilities, ensure_ascii=False), []

    async def build_system_prompt(
        self,
        question: Optional[str] = None,
        most_recent_memories: Optional[str] = None,
        resource_vars: Optional[Dict] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: bool = False,
    ):
        """Build system prompt."""
        system_prompt = None
        if self.bind_prompt:
            prompt_param = {}
            if resource_vars:
                prompt_param.update(resource_vars)
            if context:
                prompt_param.update(context)
            if self.bind_prompt.template_format == "f-string":
                system_prompt = self.bind_prompt.template.format(
                    **prompt_param,
                )
            elif self.bind_prompt.template_format == "jinja2":
                system_prompt = Template(self.bind_prompt.template).render(prompt_param)
            else:
                logger.warning("Bind prompt template not exsit or  format not support!")
        if not system_prompt:
            param: Dict = context if context else {}
            system_prompt = await self.build_prompt(
                question=question,
                is_system=True,
                most_recent_memories=most_recent_memories,
                resource_vars=resource_vars,
                is_retry_chat=is_retry_chat,
                **param,
            )
        return system_prompt

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
                if not last_out.terminate:
                    self.profile.system_prompt_template = _DEEPSEARCH_FINIAL_SUMMARY_TEMPLATE
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
        # messages = []
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

        # for mem_dict in structured_memories:
        #     question = mem_dict.get("question")
        #     thought = mem_dict.get("thought")
        #     action = mem_dict.get("action")
        #     action_input = mem_dict.get("action_input")
        #     observation = mem_dict.get("observation")
        #     if question:
        #         messages.append(
        #             AgentMessage(
        #                 content=f"Question: {question}",
        #                 role=ModelMessageRoleType.HUMAN,
        #             )
        #         )
        #     ai_content = []
        #     if thought:
        #         ai_content.append(f"Thought: {thought}")
        #     if action:
        #         ai_content.append(f"Action: {action}")
        #     if action_input:
        #         ai_content.append(f"Action Input: {action_input}")
        #     messages.append(
        #         AgentMessage(
        #             content="\n".join(ai_content),
        #             role=ModelMessageRoleType.AI,
        #         )
        #     )
        #
        #     if observation:
        #         messages.append(
        #             AgentMessage(
        #                 content=f"Observation: {observation}",
        #                 role=ModelMessageRoleType.HUMAN,
        #             )
        #         )
        #
        # if not messages and not_json_memories:
        #     messages.append(
        #         AgentMessage(
        #             content="\n".join(not_json_memories),
        #             role=ModelMessageRoleType.HUMAN,
        #         )
        #     )
        return "\n".join([
            mem_dict.get("observation") for mem_dict in structured_memories
        ])
