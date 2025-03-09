import json
import logging
from typing import Any, List, Optional, Tuple

from dbgpt.agent import (
    ActionOutput,
    Agent,
    AgentMemoryFragment,
    AgentMessage,
    ConversableAgent,
    ProfileConfig,
    ResourceType,
)
from dbgpt.agent.expand.actions.react_action import ReActAction
from dbgpt.core import ModelMessageRoleType
from dbgpt.util.configure import DynConfig
from dbgpt.util.json_utils import find_json_objects

logger = logging.getLogger(__name__)
_REACT_SYSTEM_TEMPLATE = """\
You are a {{ role }}, {% if name %}named {{ name }}.
{% endif %}your goal is {% if is_retry_chat %}{{ retry_goal }}
{% else %}{{ goal }}
{% endif %}.\
At the same time, please strictly abide by the constraints and specifications 
in the "IMPORTANT REMINDER" below.
{% if resource_prompt %}\
# ACTION SPACE #
{{ resource_prompt }} 
{% endif %}
{% if expand_prompt %}\
{{ expand_prompt }} 
{% endif %}\


# IMPORTANT REMINDER #
The current time is:{{now_time}}.
{% if constraints %}\
{% for constraint in constraints %}\
{{ loop.index }}. {{ constraint }}
{% endfor %}\
{% endif %}\


{% if is_retry_chat %}\
{% if retry_constraints %}\
{% for retry_constraint in retry_constraints %}\
{{ loop.index }}. {{ retry_constraint }}
{% endfor %}\
{% endif %}\
{% else %}\



{% endif %}\



{% if examples %}\
# EXAMPLE INTERACTION #
You can refer to the following examples:
{{ examples }}\
{% endif %}\

{% if most_recent_memories %}\
# History of Solving Task#
{{ most_recent_memories }}\
{% endif %}\

# RESPONSE FORMAT # 
{% if out_schema %} {{ out_schema }} {% endif %}\

################### TASK ###################
Please solve the task:
"""


_REACT_WRITE_MEMORY_TEMPLATE = """\
{% if question %}Question: {{ question }} {% endif %}
{% if assistant %}Assistant: {{ assistant }} {% endif %}
{% if observation %}Observation: {{ observation }} {% endif %}
"""


class ReActAgent(ConversableAgent):
    end_action_name: str = DynConfig(
        "terminate",
        category="agent",
        key="dbgpt_agent_expand_plugin_assistant_agent_end_action_name",
    )
    max_steps: int = DynConfig(
        10,
        category="agent",
        key="dbgpt_agent_expand_plugin_assistant_agent_max_steps",
    )
    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "ReAct",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_name",
        ),
        role=DynConfig(
            "ToolMaster",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_role",
        ),
        goal=DynConfig(
            "Read and understand the tool information given in the action space "
            "below to understand their capabilities and how to use them,and choosing "
            "the right tool to solve the task",
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_goal",
        ),
        constraints=DynConfig(
            [
                "Achieve the goal step by step."
                "Each step, please read the parameter definition of the tool carefully "
                "and extract the specific parameters required to execute the tool "
                "from the user's goal.",
                "information in json format according to the following required format."
                "If there is an example, please refer to the sample format output.",
                "each step, you can only select one tool in action space.",
            ],
            category="agent",
            key="dbgpt_agent_expand_plugin_assistant_agent_constraints",
        ),
        system_prompt_template=_REACT_SYSTEM_TEMPLATE,
        write_memory_template=_REACT_WRITE_MEMORY_TEMPLATE,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([ReActAction])

    async def review(self, message: Optional[str], censored: Agent) -> Tuple[bool, Any]:
        """Review the message based on the censored message."""
        try:
            json_obj = find_json_objects(message)
            if len(json_obj) == 0:
                raise ValueError(
                    "No correct json object found in the message。"
                    "Please strictly output JSON in the defined "
                    "format, and only one action can be ouput each time. "
                )
            return True, json_obj[0]
        except Exception as e:
            logger.error(f"review error: {e}")
            raise e

    def validate_action(self, action_name: str) -> bool:
        tools = self.resource.get_resource_by_type(ResourceType.Tool)
        for tool in tools:
            if tool.name == action_name:
                return True
        raise ValueError(f"{action_name} is not in the action space.")

    async def generate_reply(
        self,
        received_message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> AgentMessage:
        """Generate a reply based on the received messages."""
        try:
            logger.info(
                f"generate agent reply!sender={sender}, "
                f"rely_messages_len={rely_messages}"
            )
            self.validate_action(self.end_action_name)
            observation = AgentMessage(content="please start!")
            reply_message: AgentMessage = self._init_reply_message(
                received_message=received_message
            )
            thinking_messages, resource_info = await self._load_thinking_messages(
                received_message=observation,
                sender=sender,
                rely_messages=rely_messages,
                historical_dialogues=historical_dialogues,
                context=reply_message.get_dict_context(),
                is_retry_chat=is_retry_chat,
            )
            # attach current task to system prompt
            thinking_messages[0].content = (
                thinking_messages[0].content + "\n" + received_message.content
            )
            done = False
            max_steps = self.max_steps
            await self.write_memories(
                question=received_message.content,
                ai_message="",
            )
            while not done and max_steps > 0:
                ai_message = ""
                try:
                    # 1. thinking
                    llm_reply, model_name = await self.thinking(
                        thinking_messages, sender
                    )
                    reply_message.model_name = model_name
                    reply_message.resource_info = resource_info
                    ai_message = llm_reply
                    thinking_messages.append(
                        AgentMessage(role=ModelMessageRoleType.AI, content=llm_reply)
                    )
                    approve, json_obj = await self.review(llm_reply, self)
                    logger.info(f"jons_obj: {json_obj}")
                    action = json_obj["Action"]
                    thought = json_obj["Thought"]
                    action.update({"thought": thought})
                    reply_message.content = json.dumps(action, ensure_ascii=False)
                    tool_name = action["tool_name"]
                    self.validate_action(tool_name)
                    # 2. act
                    act_extent_param = self.prepare_act_param(
                        received_message=received_message,
                        sender=sender,
                        rely_messages=rely_messages,
                        historical_dialogues=historical_dialogues,
                    )
                    act_out: ActionOutput = await self.act(
                        message=reply_message,
                        sender=sender,
                        reviewer=reviewer,
                        is_retry_chat=is_retry_chat,
                        last_speaker_name=last_speaker_name,
                        **act_extent_param,
                    )
                    if act_out:
                        reply_message.action_report = act_out

                    # 3. obs
                    check_pass, reason = await self.verify(
                        reply_message, sender, reviewer
                    )
                    done = tool_name == self.end_action_name and check_pass
                    if check_pass:
                        logger.info(f"Observation:{act_out.content}")
                        thinking_messages.append(
                            AgentMessage(
                                role=ModelMessageRoleType.HUMAN,
                                content=f"Observation: {tool_name} "
                                f"output:{act_out.content}\n",
                            )
                        )
                        await self.write_memories(
                            question="",
                            ai_message=ai_message,
                            action_output=act_out,
                            check_pass=check_pass,
                        )
                    else:
                        observation = f"Observation: {reason}"
                        logger.info(f"Observation:{observation}")
                        thinking_messages.append(
                            AgentMessage(
                                role=ModelMessageRoleType.HUMAN, content=observation
                            )
                        )
                        await self.write_memories(
                            question="",
                            ai_message=ai_message,
                            check_pass=check_pass,
                            check_fail_reason=reason,
                        )
                    max_steps -= 1
                except Exception as e:
                    fail_reason = (
                        f"Observation: Exception occurs：({type(e).__name__}){e}."
                    )
                    logger.error(fail_reason)
                    thinking_messages.append(
                        AgentMessage(
                            role=ModelMessageRoleType.HUMAN, content=fail_reason
                        )
                    )
                    await self.write_memories(
                        question="",
                        ai_message=ai_message,
                        check_pass=False,
                        check_fail_reason=fail_reason,
                    )
            reply_message.success = done
            await self.adjust_final_message(True, reply_message)
            return reply_message
        except Exception as e:
            logger.exception("Generate reply exception!")
            err_message = AgentMessage(content=str(e))
            err_message.success = False
            return err_message

    async def write_memories(
        self,
        question: str,
        ai_message: str,
        action_output: Optional[ActionOutput] = None,
        check_pass: bool = True,
        check_fail_reason: Optional[str] = None,
    ) -> None:
        """Write the memories to the memory.

        We suggest you to override this method to save the conversation to memory
        according to your needs.

        Args:
            question(str): The question received.
            ai_message(str): The AI message, LLM output.
            action_output(ActionOutput): The action output.
            check_pass(bool): Whether the check pass.
            check_fail_reason(str): The check fail reason.
        """
        observation = ""
        if action_output and action_output.observations:
            observation = action_output.observations
        elif check_fail_reason:
            observation = check_fail_reason
        memory_map = {
            "question": question,
            "assistant": ai_message,
            "observation": observation,
        }
        write_memory_template = self.write_memory_template
        memory_content = self._render_template(write_memory_template, **memory_map)
        fragment = AgentMemoryFragment(memory_content)
        await self.memory.write(fragment)
