import json
import logging
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

from ...core import ModelMessageRoleType
from .actions.react_action import ReActAction, Terminate

logger = logging.getLogger(__name__)

_DATA_AGENT_DEFAULT_GOAL = """You are an intelligent data analysis agent that can
autonomously plan and execute data analysis tasks.
Your goal is to understand data analysis requirements, create analysis plans,
and execute them systematically.

# Planning Process #
1. Understand the analysis objective and requirements
2. Examine available data sources and structure
3. Create a step-by-step analysis plan
4. Execute the plan using appropriate tools
5. Generate insights and visualizations
6. Provide comprehensive results and recommendations

# Action Space Simple Description #
{{ action_space_simple_desc }}
"""

_DATA_AGENT_SYSTEM_TEMPLATE = """\
You are a {{ role }}, {% if name %}named {{ name }}. {% endif %}\
{{ goal }}

You are an expert data analyst with strong planning and execution capabilities. 
For each data analysis task, you should:

1. **Planning Phase**: 
   - Understand the business question or analysis objective
   - Identify required data and available data sources
   - Create a systematic analysis plan with clear steps
   - Consider potential challenges and alternative approaches

2. **Execution Phase**:
   - Load and explore the data systematically
   - Perform data cleaning and preprocessing as needed
   - Apply appropriate analysis techniques (statistical analysis, visualization, etc.)
   - Generate meaningful insights and recommendations

3. **Communication Phase**:
   - Present findings clearly with supporting evidence
   - Provide visualizations when helpful
   - Suggest next steps or further analysis opportunities

You can only use one action in the actions provided in the ACTION SPACE to solve the \
task. For each step, you must output an Action; it cannot be empty. The maximum number \
of steps you can take is {{ max_steps }}.

# ACTION SPACE #
{{ action_space }}

# RESPONSE FORMAT # 
For each task input, your response should contain:
1. Thought: Your analysis of the task, planning considerations, and reasoning for
the next action
2. Phase: A short phrase describing the intent or stage of this step
(e.g. "探索数据源结构", "加载数据并初步分析", "执行数据清洗脚本", "生成分析报告")
3. Action: The selected action from the ACTION SPACE
4. Action Input: Parameters required for the action (can be empty if no input needed)

# PLANNING EXAMPLE #
Thought: I need to analyze sales data to identify trends and provide insights.
First, I should examine the available data sources to understand the data structure
and then create a comprehensive analysis plan.
Phase: 分析销售数据结构与来源
Action: examine_data_sources
Action Input: {}

# EXECUTION EXAMPLE #
Thought: Now that I understand the data structure, I'll load the sales data and
perform initial exploratory analysis to identify patterns and trends.
Phase: 加载数据并初步分析
Action: load_data
Action Input: {"source": "sales_data", "analysis_type": "exploratory"}

################### TASK ###################
Please solve this data analysis task:

{{ question }}

Please answer in the same language as the user's question.
The current time is: {{ now_time }}.
"""

_DATA_AGENT_WRITE_MEMORY_TEMPLATE = """\
{% if question %}Question: {{ question }} {% endif %}
{% if thought %}Thought: {{ thought }} {% endif %}
{% if phase %}Phase: {{ phase }} {% endif %}
{% if action %}Action: {{ action }} {% endif %}
{% if action_input %}Action Input: {{ action_input }} {% endif %}
{% if observation %}Observation: {{ observation }} {% endif %}
{% if plan %}Analysis Plan: {{ plan }} {% endif %}
"""


class DataAnalysisPlanningAgent(ConversableAgent):
    """Data Analysis Agent with autonomous planning capabilities."""

    max_retry_count: int = 20
    run_mode: AgentRunMode = AgentRunMode.LOOP

    # Planning state
    analysis_plan: Optional[List[Dict[str, Any]]] = Field(default=None)
    current_step: int = Field(default=0)
    planning_complete: bool = Field(default=False)

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "DataAnalysisPlanningAgent",
            category="agent",
            key="dbgpt_agent_data_analysis_planning_agent_name",
        ),
        role=DynConfig(
            "SeniorDataAnalyst",
            category="agent",
            key="dbgpt_agent_data_analysis_planning_agent_role",
        ),
        goal=DynConfig(
            _DATA_AGENT_DEFAULT_GOAL,
            category="agent",
            key="dbgpt_agent_data_analysis_planning_agent_goal",
        ),
        system_prompt_template=_DATA_AGENT_SYSTEM_TEMPLATE,
        user_prompt_template="",
        write_memory_template=_DATA_AGENT_WRITE_MEMORY_TEMPLATE,
    )
    parser: ReActOutputParser = Field(default_factory=ReActOutputParser)

    def __init__(self, **kwargs):
        """Initialize Data Analysis Planning Agent."""
        super().__init__(**kwargs)
        self._init_actions([ReActAction, Terminate])
        self._reset_planning_state()

    def _reset_planning_state(self):
        """Reset planning state for new tasks."""
        self.analysis_plan = None
        self.current_step = 0
        self.planning_complete = False

    async def _a_init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        reply_message = super()._init_reply_message(received_message, rely_messages)

        tool_packs = ToolPack.from_resource(self.resource)
        action_space = []
        action_space_names = []
        action_space_simple_desc = []

        # Add data analysis specific actions
        data_analysis_actions = [
            "create_analysis_plan: Create a systematic plan for data analysis",
            "examine_data_sources: Explore available data sources and their structure",
            "load_data: Load data from specified sources for analysis",
            "clean_data: Perform data cleaning and preprocessing",
            "explore_data: Conduct exploratory data analysis",
            "statistical_analysis: Perform statistical tests and analysis",
            "create_visualization: Generate charts and visualizations",
            "generate_insights: Extract and present key insights",
            "validate_results: Validate analysis results and methodology",
        ]

        if tool_packs:
            tool_pack = tool_packs[0]
            for tool in tool_pack.sub_resources:
                tool_desc, _ = await tool.get_prompt(lang=self.language)
                action_space_names.append(tool.name)
                action_space.append(tool_desc)
                if isinstance(tool, BaseTool):
                    tool_simple_desc = tool.description
                else:
                    tool_simple_desc = tool.get_prompt()
                action_space_simple_desc.append(f"{tool.name}: {tool_simple_desc}")
        else:
            # Include default data analysis actions
            for action_desc in data_analysis_actions:
                action_name = action_desc.split(":")[0]
                action_space_names.append(action_name)
                action_space.append(action_desc)
                action_space_simple_desc.append(action_desc)

            for action in self.actions:
                action_space_names.append(action.name)
                action_space.append(action.get_action_description())

        reply_message.context = {
            "max_steps": self.max_retry_count,
            "action_space": "\n".join(action_space),
            "action_space_names": ", ".join(action_space_names),
            "action_space_simple_desc": "\n".join(action_space_simple_desc),
        }
        return reply_message

    async def preload_resource(self) -> None:
        await super().preload_resource()
        self._check_and_add_terminate()

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
            self.resource.apply(apply_pack_func=_add_terminate)

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load agent bind resource."""
        if self.resource:

            def _remove_tool(r: Resource):
                if r.type() == ResourceType.Tool:
                    return None
                return r

            new_resource = self.resource.apply(apply_func=_remove_tool)
            if new_resource:
                resource_prompt, resource_reference = await new_resource.get_prompt(
                    lang=self.language, question=question
                )
                return resource_prompt, resource_reference
        return None, None

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
        """Perform actions with planning capabilities."""
        message_content = message.content
        if not message_content:
            raise ValueError("The response is empty.")

        try:
            steps = self.parser.parse_current_step(message_content)
            err_msg = None
            if not steps:
                err_msg = (
                    "No correct response found. Please check your response, which must"
                    " be in the format indicated in the system prompt."
                )
            elif len(steps) != 1:
                err_msg = "Only one action is allowed each time."
            if err_msg:
                return ActionOutput(is_exe_success=False, content=err_msg)
        except Exception as e:
            logger.warning(f"review error: {e}")

        action_output = await super().act(
            message=message,
            sender=sender,
            reviewer=reviewer,
            is_retry_chat=is_retry_chat,
            last_speaker_name=last_speaker_name,
            **kwargs,
        )

        # Update planning state based on action results
        if action_output.is_exe_success:
            await self._update_planning_state(action_output)

        return action_output

    async def _update_planning_state(self, action_output: ActionOutput):
        """Update planning state based on action output."""
        # This can be extended to track planning progress
        if hasattr(action_output, "action") and action_output.action:
            if action_output.action == "create_analysis_plan":
                self.planning_complete = True
                # Could parse and store the plan here
            elif action_output.action in [
                "load_data",
                "explore_data",
                "statistical_analysis",
            ]:
                self.current_step += 1

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
            plan = mem_dict.get("plan")

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
            if plan:
                ai_content.append(f"Analysis Plan: {plan}")
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
