import logging
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

from dbgpt.core.interface.message import ModelMessageRoleType

from ..common.schema import Status
from ..memory.base import GptsPlan
from ..memory.gpts_memory import GptsMemory
from .agent import Agent, AgentContext
from .base_agent import ConversableAgent

logger = logging.getLogger(__name__)


@dataclass
class PlanChat:
    """(In preview) A group chat class that contains the following data fields:
    - agents: a list of participating agents.
    - messages: a list of messages in the group chat.
    - max_round: the maximum number of rounds.
    - admin_name: the name of the admin agent if there is one. Default is "Admin".
        KeyBoardInterrupt will make the admin agent take over.
    - func_call_filter: whether to enforce function call filter. Default is True.
        When set to True and when a message is a function call suggestion,
        the next speaker will be chosen from an agent which contains the corresponding function name
        in its `function_map`.
    - speaker_selection_method: the method for selecting the next speaker. Default is "auto".
        Could be any of the following (case insensitive), will raise ValueError if not recognized:
        - "auto": the next speaker is selected automatically by LLM.
        - "manual": the next speaker is selected manually by user input.
        - "random": the next speaker is selected randomly.
        - "round_robin": the next speaker is selected in a round robin fashion, i.e., iterating in the same order as provided in `agents`.
    - allow_repeat_speaker: whether to allow the same speaker to speak consecutively. Default is True.
    """

    agents: List[Agent]
    messages: List[Dict]
    max_round: int = 50
    admin_name: str = "Admin"
    func_call_filter: bool = True
    speaker_selection_method: str = "auto"
    allow_repeat_speaker: bool = True

    _VALID_SPEAKER_SELECTION_METHODS = ["auto", "manual", "random", "round_robin"]

    @property
    def agent_names(self) -> List[str]:
        """Return the names of the agents in the group chat."""
        return [agent.name for agent in self.agents]

    def reset(self):
        """Reset the group chat."""
        self.messages.clear()

    def agent_by_name(self, name: str) -> Agent:
        """Returns the agent with a given name."""
        return self.agents[self.agent_names.index(name)]

    # def select_speaker_msg(self, agents: List[Agent], task_context: str, models: Optional[List[dict]]):
    #     f"""Return the message for selecting the next speaker."""
    #     return f"""You are in a role play game. Read and understand the following tasks and assign the appropriate role to complete them.
    #     Task content: {task_context}
    #     You can fill the following roles: {[agent.name for agent in agents]},
    #     Please answer only the role name, such as: {agents[0].name}"""

    def select_speaker_msg(self, agents: List[Agent]):
        """Return the message for selecting the next speaker."""
        return f"""You are in a role play game. The following roles are available:
    {self._participant_roles(agents)}.
    Read the following conversation.
    Then select the next role from {[agent.name for agent in agents]} to play. The role can be selected repeatedly.Only return the role."""

    async def a_select_speaker(
        self,
        last_speaker: Agent,
        selector: ConversableAgent,
        now_plan_context: str,
        pre_allocated: str = None,
    ):
        """Select the next speaker."""
        if (
            self.speaker_selection_method.lower()
            not in self._VALID_SPEAKER_SELECTION_METHODS
        ):
            raise ValueError(
                f"GroupChat speaker_selection_method is set to '{self.speaker_selection_method}'. "
                f"It should be one of {self._VALID_SPEAKER_SELECTION_METHODS} (case insensitive). "
            )

        agents = self.agents
        n_agents = len(agents)
        # Warn if GroupChat is underpopulated

        if (
            n_agents <= 2
            and self.speaker_selection_method.lower() != "round_robin"
            and self.allow_repeat_speaker
        ):
            logger.warning(
                f"GroupChat is underpopulated with {n_agents} agents. "
                "It is recommended to set speaker_selection_method to 'round_robin' or allow_repeat_speaker to False."
                "Or, use direct communication instead."
            )

        # remove the last speaker from the list to avoid selecting the same speaker if allow_repeat_speaker is False
        agents = (
            agents
            if self.allow_repeat_speaker
            else [agent for agent in agents if agent != last_speaker]
        )

        # if self.speaker_selection_method.lower() == "manual":
        #     selected_agent = self.manual_select_speaker(agents)
        #     if selected_agent:
        #         return selected_agent
        # elif self.speaker_selection_method.lower() == "round_robin":
        #     return self.next_agent(last_speaker, agents)
        # elif self.speaker_selection_method.lower() == "random":
        #     return random.choice(agents)

        if pre_allocated:
            # Preselect speakers
            logger.info(f"Preselect speakers:{pre_allocated}")
            name = pre_allocated
            model = None
        else:
            # auto speaker selection
            selector.update_system_message(self.select_speaker_msg(agents))
            final, name, model = await selector.a_generate_oai_reply(
                self.messages
                + [
                    {
                        "role": ModelMessageRoleType.HUMAN,
                        "content": f"""Read and understand the following task content and assign the appropriate role to complete the task.
                                    Task content: {now_plan_context}
                                    select the role from: {[agent.name for agent in agents]},
                                    Please only return the role, such as: {agents[0].name}""",
                    }
                ]
            )
            if not final:
                # the LLM client is None, thus no reply is generated. Use round robin instead.
                return self.next_agent(last_speaker, agents), model

        # If exactly one agent is mentioned, use it. Otherwise, leave the OAI response unmodified
        mentions = self._mentioned_agents(name, agents)
        if len(mentions) == 1:
            name = next(iter(mentions))
        else:
            logger.warning(
                f"GroupChat select_speaker failed to resolve the next speaker's name. This is because the speaker selection OAI call returned:\n{name}"
            )

        # Return the result
        try:
            return self.agent_by_name(name), model
        except Exception as e:
            logger.warning(f"auto select speaker failed!{str(e)}")
            return self.next_agent(last_speaker, agents), model

    def _mentioned_agents(self, message_content: str, agents: List[Agent]) -> Dict:
        """
        Finds and counts agent mentions in the string message_content, taking word boundaries into account.

        Returns: A dictionary mapping agent names to mention counts (to be included, at least one mention must occur)
        """
        mentions = dict()
        for agent in agents:
            regex = (
                r"(?<=\W)" + re.escape(agent.name) + r"(?=\W)"
            )  # Finds agent mentions, taking word boundaries into account
            count = len(
                re.findall(regex, " " + message_content + " ")
            )  # Pad the message to help with matching
            if count > 0:
                mentions[agent.name] = count
        return mentions

    def _participant_roles(self, agents: List[Agent] = None) -> str:
        # Default to all agents registered
        if agents is None:
            agents = self.agents

        roles = []
        for agent in agents:
            if agent.system_message.strip() == "":
                logger.warning(
                    f"The agent '{agent.name}' has an empty system_message, and may not work well with GroupChat."
                )
            roles.append(f"{agent.name}: {agent.describe}")
        return "\n".join(roles)

    def agent_by_name(self, name: str) -> Agent:
        """Returns the agent with a given name."""
        return self.agents[self.agent_names.index(name)]

    def next_agent(self, agent: Agent, agents: List[Agent]) -> Agent:
        """Return the next agent in the list."""
        if agents == self.agents:
            return agents[(self.agent_names.index(agent.name) + 1) % len(agents)]
        else:
            offset = self.agent_names.index(agent.name) + 1
            for i in range(len(self.agents)):
                if self.agents[(offset + i) % len(self.agents)] in agents:
                    return self.agents[(offset + i) % len(self.agents)]


class PlanChatManager(ConversableAgent):
    """(In preview) A chat manager agent that can manage a group chat of multiple agents."""

    NAME = "plan_manager"

    def __init__(
        self,
        plan_chat: PlanChat,
        planner: Agent,
        memory: GptsMemory,
        agent_context: "AgentContext",
        # unlimited consecutive auto reply by default
        max_consecutive_auto_reply: Optional[int] = sys.maxsize,
        human_input_mode: Optional[str] = "NEVER",
        describe: Optional[str] = "Plan chat manager.",
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            describe=describe,
            memory=memory,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )
        # Order of register_reply is important.

        # Allow async chat if initiated using a_initiate_chat
        self.register_reply(
            Agent,
            PlanChatManager.a_run_chat,
            config=plan_chat,
            reset_config=PlanChat.reset,
        )
        self.plan_chat = plan_chat
        self.planner = planner

    async def a_reasoning_reply(
        self, messages: Optional[List[Dict]] = None
    ) -> Union[str, Dict, None]:
        if messages is None or len(messages) <= 0:
            message = None
            return None, None
        else:
            message = messages[-1]
            self.plan_chat.messages.append(message)
            return message["content"], None

    async def a_process_rely_message(
        self, conv_id: str, now_plan: GptsPlan, speaker: ConversableAgent
    ):
        rely_prompt = ""
        speaker.reset_rely_message()
        if now_plan.rely and len(now_plan.rely) > 0:
            rely_tasks_list = now_plan.rely.split(",")
            rely_tasks = self.memory.plans_memory.get_by_conv_id_and_num(
                conv_id, rely_tasks_list
            )
            if rely_tasks:
                rely_prompt = "Read the result data of the dependent steps in the above historical message to complete the current goal:"
                for rely_task in rely_tasks:
                    speaker.append_rely_message(
                        {"content": rely_task.sub_task_content},
                        ModelMessageRoleType.HUMAN,
                    )
                    speaker.append_rely_message(
                        {"content": rely_task.result}, ModelMessageRoleType.AI
                    )
        return rely_prompt

    async def a_verify_reply(
        self, message: Optional[Dict], sender: "Agent", reviewer: "Agent", **kwargs
    ) -> Union[str, Dict, None]:
        return True, message

    async def a_run_chat(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Agent = None,
        config: Optional[PlanChat] = None,
    ):
        """Run a group chat asynchronously."""

        speaker = sender
        groupchat = config

        final_message = None

        for i in range(groupchat.max_round):
            plans = self.memory.plans_memory.get_by_conv_id(self.agent_context.conv_id)
            if not plans or len(plans) <= 0:
                ###Have no plan, generate a new plan TODO init plan use planmanger
                await self.a_send(
                    {"content": message, "current_gogal": message},
                    self.planner,
                    reviewer,
                    request_reply=False,
                )
                verify_pass, reply = await self.planner.a_generate_reply(
                    {"content": message, "current_gogal": message}, self, reviewer
                )

                await self.planner.a_send(
                    message=reply,
                    recipient=self,
                    reviewer=reviewer,
                    request_reply=False,
                )
                if not verify_pass:
                    final_message = reply
                    if i > 10:
                        break
            else:
                todo_plans = [
                    plan
                    for plan in plans
                    if plan.state in [Status.TODO.value, Status.RETRYING.value]
                ]
                if not todo_plans or len(todo_plans) <= 0:
                    ### The plan has been fully executed and a success message is sent to the user.
                    # complete
                    complete_message = {"content": f"TERMINATE", "is_exe_success": True}
                    return True, complete_message
                else:
                    now_plan: GptsPlan = todo_plans[0]

                    # There is no need to broadcast the message to other agents, it will be automatically obtained from the collective memory according to the dependency relationship.
                    try:
                        if Status.RETRYING.value == now_plan.state:
                            if now_plan.retry_times <= now_plan.max_retry_times:
                                current_goal_message = {
                                    "content": now_plan.result,
                                    "current_gogal": now_plan.sub_task_content,
                                    "context": {
                                        "plan_task": now_plan.sub_task_content,
                                        "plan_task_num": now_plan.sub_task_num,
                                    },
                                }
                            else:
                                self.memory.plans_memory.update_task(
                                    self.agent_context.conv_id,
                                    now_plan.sub_task_num,
                                    Status.FAILED.value,
                                    now_plan.retry_times + 1,
                                    speaker.name,
                                    "",
                                    plan_result,
                                )
                                faild_report = {
                                    "content": f"ReTask [{now_plan.sub_task_content}] was retried more than the maximum number of times and still failed.{now_plan.result}",
                                    "is_exe_success": False,
                                }
                                return True, faild_report
                        else:
                            current_goal_message = {
                                "content": now_plan.sub_task_content,
                                "current_gogal": now_plan.sub_task_content,
                                "context": {
                                    "plan_task": now_plan.sub_task_content,
                                    "plan_task_num": now_plan.sub_task_num,
                                },
                            }

                        # select the next speaker
                        speaker, model = await groupchat.a_select_speaker(
                            speaker,
                            self,
                            now_plan.sub_task_content,
                            now_plan.sub_task_agent,
                        )
                        # Tell the speaker the dependent history information
                        rely_prompt = await self.a_process_rely_message(
                            conv_id=self.agent_context.conv_id,
                            now_plan=now_plan,
                            speaker=speaker,
                        )

                        current_goal_message["content"] = (
                            rely_prompt + current_goal_message["content"]
                        )

                        is_recovery = False
                        if message == current_goal_message["content"]:
                            is_recovery = True
                        await self.a_send(
                            message=current_goal_message,
                            recipient=speaker,
                            reviewer=reviewer,
                            request_reply=False,
                            is_recovery=is_recovery,
                        )
                        verify_pass, reply = await speaker.a_generate_reply(
                            current_goal_message, self, reviewer
                        )

                        plan_result = ""

                        if verify_pass:
                            if reply:
                                action_report = reply.get("action_report", None)
                                if action_report:
                                    plan_result = action_report.get("content", "")
                            ### The current planned Agent generation verification is successful
                            ##Plan executed successfully
                            self.memory.plans_memory.complete_task(
                                self.agent_context.conv_id,
                                now_plan.sub_task_num,
                                plan_result,
                            )
                            await speaker.a_send(
                                reply, self, reviewer, request_reply=False
                            )
                        else:
                            plan_result = reply["content"]
                            self.memory.plans_memory.update_task(
                                self.agent_context.conv_id,
                                now_plan.sub_task_num,
                                Status.RETRYING.value,
                                now_plan.retry_times + 1,
                                speaker.name,
                                "",
                                plan_result,
                            )
                    except Exception as e:
                        logger.exception(
                            f"An exception was encountered during the execution of the current plan step.{str(e)}"
                        )
                        error_report = {
                            "content": f"An exception was encountered during the execution of the current plan step.{str(e)}",
                            "is_exe_success": False,
                        }
                        return True, error_report

        return True, {
            "content": f"Maximum number of dialogue rounds exceeded.{self.MAX_CONSECUTIVE_AUTO_REPLY}",
            "is_exe_success": False,
        }
