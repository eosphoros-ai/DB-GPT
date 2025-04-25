import json
import logging
from typing import Any, Dict, List, Optional, Tuple

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
)
from dbgpt.agent.core.role import AgentRunMode
from dbgpt.agent.resource import BaseTool, ResourcePack, ToolPack
from dbgpt.agent.util.react_parser import ReActOutputParser
from dbgpt.util.configure import DynConfig

from ...core import ModelMessageRoleType
from .actions.react_action import ReActAction, Terminate

logger = logging.getLogger(__name__)

_REACT_DEFAULT_GOAL = """Answer the following questions or solve the tasks by \
selecting the right ACTION from the ACTION SPACE as best as you can. 
# ACTION SPACE Simple Description #
{{ action_space_simple_desc }}
"""

_REACT_SYSTEM_TEMPLATE = """\
You are a {{ role }}, {% if name %}named {{ name }}. {% endif %}\
{{ goal }}

You can only use one action in the actions provided in the ACTION SPACE to solve the \
task. For each step, you must output an Action; it cannot be empty. The maximum number \
of steps you can take is {{ max_steps }}.
Do not output an empty string!

# ACTION SPACE #
{{ action_space }}

# RESPONSE FROMAT # 
For each task input, your response should contain:
1. One analysis of the task and the current environment, reasoning to determine the \
next action (prefix "Thought: ").
2. One action string in the ACTION SPACE (prefix "Action: "), should be one of \
[{{ action_space_names }}].
3. One action input (prefix "Action Input: "), empty if no input is required.

# EXAMPLE INTERACTION #
Observation: ...(This is output provided by the external environment or Action output, \
you are not allowed to generate it.)

Thought: ...
Action: ...
Action Input: ...

################### TASK ###################
Please Solve this task:

{{ question }}\

Please answer in the same language as the user's question.
The current time is: {{ now_time }}.
"""
_REACT_USER_TEMPLATE = """\
{% if most_recent_memories %}\
Most recent message:
{{ most_recent_memories }}
{% endif %}\
"""


_REACT_WRITE_MEMORY_TEMPLATE = """\
{% if question %}Question: {{ question }} {% endif %}
{% if thought %}Thought: {{ thought }} {% endif %}
{% if action %}Action: {{ action }} {% endif %}
{% if action_input %}Action Input: {{ action_input }} {% endif %}
{% if observation %}Observation: {{ observation }} {% endif %}
"""


class ReActAgent(ConversableAgent):
    max_retry_count: int = 15
    run_mode: AgentRunMode = AgentRunMode.LOOP

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "ReAct",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_name",
        ),
        role=DynConfig(
            "ReActToolMaster",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_role",
        ),
        goal=DynConfig(
            _REACT_DEFAULT_GOAL,
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_goal",
        ),
        system_prompt_template=_REACT_SYSTEM_TEMPLATE,
        user_prompt_template=_REACT_USER_TEMPLATE,
        write_memory_template=_REACT_WRITE_MEMORY_TEMPLATE,
    )
    parser: ReActOutputParser = Field(default_factory=ReActOutputParser)

    def __init__(self, **kwargs):
        """Init indicator AssistantAgent."""
        super().__init__(**kwargs)

        self._init_actions([ReActAction, Terminate])

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
            for action in self.actions:
                action_space_names.append(action.name)
                action_space.append(action.get_action_description())
            # self.actions
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
            # Add terminal action to the resource
            self.resource.apply(apply_pack_func=_add_terminate)

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load agent bind resource."""
        if self.resource:

            def _remove_tool(r: Resource):
                if r.type() == ResourceType.Tool:
                    return None
                return r

            # Remove all tools from the resource
            # We will handle tools separately
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
        """Perform actions."""
        message_content = message.content
        if not message_content:
            raise ValueError("The response is empty.")
        try:
            steps = self.parser.parse(message_content)
            err_msg = None
            if not steps:
                err_msg = "No correct response found."
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
        return action_output

    async def write_memories(
        self,
        question: str,
        ai_message: str,
        action_output: Optional[ActionOutput] = None,
        check_pass: bool = True,
        check_fail_reason: Optional[str] = None,
        current_retry_counter: Optional[int] = None,
    ) -> AgentMemoryFragment:
        """Write the memories to the memory.

        We suggest you to override this method to save the conversation to memory
        according to your needs.

        Args:
            question(str): The question received.
            ai_message(str): The AI message, LLM output.
            action_output(ActionOutput): The action output.
            check_pass(bool): Whether the check pass.
            check_fail_reason(str): The check fail reason.

        Returns:
            AgentMemoryFragment: The memory fragment created.
        """
        if not action_output:
            raise ValueError("Action output is required to save to memory.")

        mem_thoughts = action_output.thoughts or ai_message
        action = action_output.action
        action_input = action_output.action_input
        observation = check_fail_reason or action_output.observations

        memory_map = {
            "thought": mem_thoughts,
            "action": action,
            "observation": observation,
        }
        if action_input:
            memory_map["action_input"] = action_input

        if current_retry_counter is not None and current_retry_counter == 0:
            memory_map["question"] = question

        memory_content = json.dumps(memory_map, ensure_ascii=False)
        # write_memory_template = self.write_memory_template
        # memory_content = self._render_template(write_memory_template, **memory_map)
        fragment = AgentMemoryFragment(memory_content)
        await self.memory.write(fragment)
        action_output.memory_fragments = {
            "memory": fragment.raw_observation,
            "id": fragment.id,
            "importance": fragment.importance,
        }
        return fragment

    async def _read_memories(self, observation: str) -> List[AgentMessage]:
        """Read the memories from the memory."""
        memories = await self.memory.read(observation)
        not_json_memories = []
        messages = []
        for m in memories:
            if m.raw_observation:
                try:
                    mem_dict = json.loads(m.raw_observation)
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
                except Exception:
                    not_json_memories.append(m.raw_observation)

        if not messages and not_json_memories:
            messages.append(
                AgentMessage(
                    content="\n".join(not_json_memories),
                    role=ModelMessageRoleType.HUMAN,
                )
            )
        return messages

    async def _load_thinking_messages(
        self,
        received_message: AgentMessage,
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: bool = False,
    ) -> Tuple[List[AgentMessage], Optional[Dict]]:
        observation = received_message.content
        if not observation:
            raise ValueError("The received message content is empty!")
        memory_list = await self._read_memories(observation)

        has_memories = True if memory_list else False
        reply_message_str = ""
        memories = ""
        if context is None:
            context = {}
        if rely_messages:
            copied_rely_messages = [m.copy() for m in rely_messages]
            # When directly relying on historical messages, use the execution result
            # content as a dependency
            for message in copied_rely_messages:
                action_report: Optional[ActionOutput] = message.action_report
                if action_report:
                    # TODO: Modify in-place, need to be optimized
                    message.content = action_report.content
                if message.name != self.role:
                    # TODO, use name
                    # Rely messages are not from the current agent
                    if message.role == ModelMessageRoleType.HUMAN:
                        reply_message_str += f"Question: {message.content}\n"
                    elif message.role == ModelMessageRoleType.AI:
                        reply_message_str += f"Observation: {message.content}\n"
        if reply_message_str:
            memories += "\n" + reply_message_str
        try:
            resource_prompt_str, resource_references = await self.load_resource(
                observation, is_retry_chat=is_retry_chat
            )
        except Exception as e:
            logger.exception(f"Load resource error！{str(e)}")
            raise ValueError(f"Load resource error！{str(e)}")

        resource_vars = await self.generate_resource_variables(resource_prompt_str)

        system_prompt = await self.build_system_prompt(
            question=observation,
            # most_recent_memories=memories,
            resource_vars=resource_vars,
            context=context,
            is_retry_chat=is_retry_chat,
        )
        user_prompt = await self.build_prompt(
            question=observation,
            is_system=False,
            # most_recent_memories=memories,
            resource_vars=resource_vars,
            **context,
        )

        agent_messages = []
        if system_prompt:
            agent_messages.append(
                AgentMessage(
                    content=system_prompt,
                    role=ModelMessageRoleType.SYSTEM,
                )
            )
        if historical_dialogues and not has_memories:
            # If we can't read the memory, we need to rely on the historical dialogue
            for i in range(len(historical_dialogues)):
                if i % 2 == 0:
                    # The even number starts, and the even number is the user
                    # information
                    message = historical_dialogues[i]
                    message.role = ModelMessageRoleType.HUMAN
                    agent_messages.append(message)
                else:
                    # The odd number is AI information
                    message = historical_dialogues[i]
                    message.role = ModelMessageRoleType.AI
                    agent_messages.append(message)
        if memory_list:
            agent_messages.extend(memory_list)

        # Current user input information
        if not user_prompt and not memory_list:
            user_prompt = f"Observation: {observation}"
        if user_prompt:
            agent_messages.append(
                AgentMessage(
                    content=user_prompt,
                    role=ModelMessageRoleType.HUMAN,
                )
            )
        return agent_messages, resource_references
