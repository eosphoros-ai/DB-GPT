import logging
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
import re
from dbgpt.agent.agents.agent import Agent, AgentContext
from dbgpt.agent.agents.bak.conversable_agent import ConversableAgent
from dbgpt.agent.common.schema import Status

from dbgpt.util.string_utils import str_to_bool
from dbgpt.agent.memory.gpts_memory import GptsMemory, GptsPlan

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
    max_round: int = 10
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



    async def a_check_plan_expected(self, all_plan_contexts: List[str], now_task_content: str, task_result: str,
                                    last_speaker: Agent, selector: ConversableAgent):
        selector.update_system_message(self.check_task_result_msg(last_speaker, all_plan_contexts))
        final, check_reult, model = await selector.a_generate_oai_reply(
            self.messages
            + [
                {
                    "role": "user",
                    "content": f"""Please understand the following task background and goals, and judge whether the generated results achieve the goals.
                    Task Background: {last_speaker.system_message}
                    Task Gogal: {now_task_content}
                    Task Result: {task_result}
                    Only True or False is returned.
                    """
                }
            ]
        )
        return str_to_bool(check_reult)


    async def a_select_speaker(self, last_speaker: Agent, selector: ConversableAgent, now_plan_context: str, pre_allocated: str = None):
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
                        "role": "user",
                        "content": f"""Read and understand the following task content and assign the appropriate role to complete the task.
                                    Task content: {now_plan_context}
                                    select the role from: {[agent.name for agent in agents]},
                                    Please only return the role, such as: {agents[0].name}"""
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
        except ValueError:
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
            count = len(re.findall(regex, " " + message_content + " "))  # Pad the message to help with matching
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
            # unlimited consecutive auto reply by default
            max_consecutive_auto_reply: Optional[int] = sys.maxsize,
            human_input_mode: Optional[str] = "NEVER",
            describe: Optional[str] = "Plan chat manager.",
            agent_context: 'AgentContext' = None,
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
        self,
        messages: Union[List[Dict]],
        sender: "Agent",
        reviewer: "Agent",
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False) -> Union[str, Dict, None]:

        message = messages[-1]
        context = message.get("context", None)
        if context:
            action_report = message.get("action_report", None)
            last_task_num = context.get("plan_task_num", None)
            if last_task_num and action_report:
                # : GptsPlan = self.memory.plans_memory.get_by_conv_id_and_num(self.agent_context.conv_id, [last_task_num])

                all_plans: list[GptsPlan] = self.memory.plans_memory.get_by_conv_id(self.agent_context.conv_id)
                run_plan = next((obj for obj in all_plans if obj.sub_task_num == last_task_num), None)

                if action_report and action_report['is_exe_success']:
                    check_succ = await self.plan_chat.a_check_plan_expected(
                        f'{[item.sub_task_content for item in all_plans]}', run_plan.sub_task_content,
                        action_report.get("content", ""), sender, self)
                    if check_succ:
                        self.memory.plans_memory.complete_task(self.agent_context.conv_id, last_task_num, action_report.get("content", ""))
                    else:
                        self.memory.plans_memory.update_task(self.agent_context.conv_id, last_task_num, Status.FAILED.value, run_plan.retry_times + 1,
                                                      sender.name,  "", action_report.get("content", ""))
                else:
                    self.memory.plans_memory.update_task(self.agent_context.conv_id, last_task_num, Status.FAILED.value, run_plan.retry_times + 1,
                                                  sender.name, "", action_report.get("content", ""))

        if message["role"] != "function":
            message["name"] = sender.name
        self.plan_chat.messages.append(message)
        return message['content'],  None

    async def a_plan_task_update(self, task_id: Optional[int], status: Optional[Status], retry_times: Optional[int],
                                 agent: Optional[str], result: Optional[str]):
        self.gpts_plans.update_task(task_id, status, retry_times, agent, result)

    async def a_plan_task_complete(self, task_id: Optional[str], result: Optional[str]):
        self.gpts_plans.complete_task(task_id, result)

    async def a_process_rely_message(self, conv_id: str, now_plan: GptsPlan, speaker: ConversableAgent):
        speaker.reset_rely_message()
        if now_plan.rely and len(now_plan.rely) > 0:
            rely_tasks_list = now_plan.rely.split(",")
            rely_tasks = self.memory.plans_memory.get_by_conv_id_and_num(conv_id, rely_tasks_list)
            if rely_tasks:
                rely_task_count = len(rely_tasks)
                for rely_task in rely_tasks:
                    speaker.append_rely_message({"content": rely_task.sub_task_content}, "user")
                    speaker.append_rely_message({"content": rely_task.result}, "assistant")

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

        plans = self.memory.plans_memory.get_by_conv_id(self.agent_context.conv_id)
        if not plans or len(plans) <= 0:
            ###Have no plan, generate a new plan
            await self.a_send({"content": message,  "current_gogal":  message}, self.planner, reviewer, request_reply=True)
        todo_plans: list[GptsPlan] = self.memory.plans_memory.get_todo_plans(self.agent_context.conv_id)

        if not todo_plans or len(todo_plans) <= 0:
            ### The plan has been fully executed and a success message is sent to the user.
            # complete
            print(f"{self.name}(to User) \n Complete!")
            return
            # await self.a_send({"content": "TERMINATE"}, sender, reviewer, request_reply=True)
        else:
            now_plan: GptsPlan = todo_plans[0]
            # process reply message

            # There is no need to broadcast the message to other agents, it will be automatically obtained from the collective memory according to the dependency relationship.
            try:
                # select the next speaker
                speaker, model = await groupchat.a_select_speaker(speaker, self, now_plan.sub_task_content, now_plan.sub_task_agent)

                await self.a_process_rely_message(conv_id=self.agent_context.conv_id, now_plan=now_plan,
                                                  speaker=speaker)

                use_cache: bool = True
                if now_plan.retry_times > 1:
                    use_cache = False
                # let the speaker speak
                await self.a_send({"content": now_plan.sub_task_content,  "current_gogal":  now_plan.sub_task_content, "model_name": model, "context": {
                    "plan_task": now_plan.sub_task_content,
                    "plan_task_num": now_plan.sub_task_num,
                    "use_cache": use_cache,
                }}, speaker, reviewer, request_reply=True)
            except KeyboardInterrupt:
                # let the admin agent speak if interrupted
                if groupchat.admin_name in groupchat.agent_names:
                    # admin agent is one of the participants
                    speaker = groupchat.agent_by_name(groupchat.admin_name)
                    await self.a_send({"content": now_plan.sub_task_content, "context": {
                        "plan_task": now_plan.sub_task_content,
                        "plan_task_num": now_plan.sub_task_num,
                        "use_cache": use_cache,
                    }}, speaker, reviewer, request_reply=True)
                else:
                    # admin agent is not found in the participants
                    raise

        return True, None
