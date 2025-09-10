import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import Field
from dbgpt.agent import (
    ActionOutput,
    ActorProxyAgent,
    AgentMessage,
    ConversableAgent,
    ProfileConfig,
    Resource,
    ResourceType,
)
from dbgpt.agent.core.role import AgentRunMode
from dbgpt.agent.resource import FunctionTool, ResourcePack, ToolPack
from dbgpt.agent.util.react_parser import ReActOutputParser
from dbgpt.util.configure import DynConfig

from ...util.tracer import root_tracer
from .actions.rag_action import AgenticRAGAction, AgenticRAGState
from .actions.react_action import Terminate

logger = logging.getLogger(__name__)

_RAG_GOAL = """Answer the following questions or solve the tasks by \
selecting the right search tools. 
"""
_AGENTIC_RAG_SYSTEM_TEMPLATE = """
你是一个答疑智能助手。
<目标>
你的任务是根据用户的问题或任务，选择合适的知识库和直接搜索工具direct来回答问题或解决问题。
</目标>
<历史记忆>
{{most_recent_memories}}
</历史记忆>

<可用工具>
1. 可用知识和工具: {{tools}}
</可用工具>

<流程>
1. 根据用户问题选择可用的知识或者工具。
</流程>

<回复格式>
严格按以下JSON格式输出，确保可直接解析：
{
  "tools": [{
    "tool": "工具的名称,可以是知识检索工具或搜索工具。",
    "args": {
      "arg_name1": "arg_value1",
      "arg_name2": "arg_value2"
    }
  }],
  "knowledge": ["knowledge_id1", "knowledge_id2"],
}
</回复格式>

注意:如果<可用工具>中没有可用的知识或工具，请返回空的"tools"和"knowledge"字段。
<问题>
{{ question }}
</问题>

当前时间是: {{ now_time }}。
"""

_AGENTIC_RAG_USER_TEMPLATE = """"""
_FINIAL_SUMMARY_TEMPLATE = """
您是一个总结专家,您的目标是 根据找到的知识或历史对话记忆
{{most_recent_memories}}
进行归纳总结，专业且有逻辑的回答用户问题。 
1.请用中文回答
2. 总结回答时请务必保留原文中的图片、引用、视频等链接内容
3. 原文中的图片、引用、视频等链接格式, 出现在原文内容中，内容后，段落中都可以认为属于原文内容，请确保在总结答案中依然输出这些内容，不要丢弃，不要修改.(参考图片链接格式：![image.png](xxx) 、普通链接格式:[xxx](xxx))
4.优先从给出的资源中总结用户问题答案，如果没有找到相关信息，则尝试从当前会话的历史对话记忆中找相关信息，忽略无关的信息.
5. 回答时总结内容需要结构良好的，中文字数不超过150字，尽可能涵盖上下文里面所有你认为有用的知识点，如果提供的资源信息带有图片![image.png](xxx) ，链接[xxx](xxx))或者表格,总结的时候也将图片，链接，表格按照markdown格式进行输出。
6. 注意需要并在每段总结的**中文**末尾结束标点符号前面注明内容来源的链接编号,语雀链接,语雀标题[i](https://yuque_url.com),i 为引用的序号，eg:1,2,3。
7. 回答的时候内容按照论文的格式格式输出，组织结构尽量结构良好。
用户问题:
"""


class RAGAgent(ConversableAgent):
    max_retry_count: int = 15
    run_mode: AgentRunMode = AgentRunMode.LOOP

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "AgenticRAG",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_name",
        ),
        role=DynConfig(
            "AgenticRAGAssistant",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_role",
        ),
        goal=DynConfig(
            _RAG_GOAL,
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_goal",
        ),
        system_prompt_template=_AGENTIC_RAG_SYSTEM_TEMPLATE,
        user_prompt_template=_AGENTIC_RAG_USER_TEMPLATE,
    )
    parser: ReActOutputParser = Field(default_factory=ReActOutputParser)
    state: str = AgenticRAGState.REFLECTION.value
    next_step_prompt = _AGENTIC_RAG_SYSTEM_TEMPLATE

    def __init__(self, **kwargs):
        """Init indicator AssistantAgent."""
        super().__init__(**kwargs)

        self._init_actions([AgenticRAGAction])

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
            "tools": resource_prompt,
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
        prompt = ""
        tool_resources = ""
        if self.resource:
            tool_packs = ToolPack.from_resource(self.resource)
            action_space = {}
            if tool_packs:
                prompt = "<tools>\n"
                tool_pack = tool_packs[0]
                for tool in tool_pack.sub_resources:
                    if isinstance(tool, FunctionTool):
                        tool_simple_desc = tool.description
                        action_space[tool.name] = tool
                        parameters_string = await self._parse_tool_args(tool)
                        prompt += (
                            f"<tool>\n"
                            f"<tool_name>{tool.name}</tool_name>\n"
                            f"<tool_desc>{tool_simple_desc}</tool_desc>\n"
                            f"<parameters>{parameters_string}</parameters>\n"
                            f"</tool>\n"
                        )
                    else:
                        tool_simple_desc = tool.get_prompt()
                        prompt += (
                            f"<tool>\n"
                            f"<tool_name>{tool.name}</tool_name>\n"
                            f"<tool_desc>{tool_simple_desc}</tool_desc>\n"
                            f"</tool>\n"
                        )

                prompt += "</tools>"
            tool_resources += prompt
            if isinstance(self.resource, ResourcePack):
                for resource in self.resource.sub_resources:
                    from dbgpt_serve.agent.resource.knowledge_pack import (
                        KnowledgePackSearchResource,
                    )

                    if isinstance(resource, KnowledgePackSearchResource):
                        tool_resources += "\n<knowledge>\n"
                        tool_resources += resource.description
                        tool_resources += "</knowledge>\n"

        return tool_resources, []

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
        if self.state == AgenticRAGState.FINAL_SUMMARIZE.value:
            next_step_prompt = _FINIAL_SUMMARY_TEMPLATE
        else:
            next_step_prompt = _AGENTIC_RAG_SYSTEM_TEMPLATE
        self.profile.system_prompt_template = next_step_prompt
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
        sender: ActorProxyAgent,
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
        sender: ActorProxyAgent,
        reviewer: Optional[ActorProxyAgent] = None,
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
                last_out = await action.run(
                    ai_message=message.content if message.content else "",
                    resource=None,
                    rely_action_out=last_out,
                    state=self.state,
                    current_goal=message.current_goal,
                    **kwargs,
                )
                self.state = last_out.state
                span.metadata["action_out"] = last_out.to_dict() if last_out else None
        if not last_out:
            raise ValueError("Action should return value！")
        return last_out

    async def _parse_tool_args(self, tool: FunctionTool) -> str:
        """解析工具参数"""
        properties = {}
        required_list = []

        for key, value in tool.args.items():
            properties[key] = {
                "type": value.type,
                "description": value.description,
            }
            if value.required:
                required_list.append(key)

        parameters_dict = {
            "type": "object",
            "properties": properties,
            "required": required_list,
        }

        return json.dumps(parameters_dict, ensure_ascii=False)
