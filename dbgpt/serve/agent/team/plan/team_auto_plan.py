import logging
import sys
from typing import Any, List, Optional

from dbgpt.agent.agents.agent import Agent, AgentContext
from dbgpt.agent.agents.agents_mange import mentioned_agents, participant_roles
from dbgpt.agent.agents.base_agent import ConversableAgent
from dbgpt.agent.agents.base_team import MangerAgent
from dbgpt.agent.common.schema import Status
from dbgpt.agent.memory.base import GptsPlan
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.core.interface.message import ModelMessageRoleType

from .planner_agent import PlannerAgent

logger = logging.getLogger(__name__)


class AutoPlanChatManager(MangerAgent):
    """(In preview) A chat manager agent that can manage a team chat of multiple agents."""

    NAME = "plan_manager"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
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
        self.register_reply(Agent, AutoPlanChatManager.a_run_chat)

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

    def select_speaker_msg(self, agents: List[Agent]):
        """Return the message for selecting the next speaker."""
        return f"""You are in a role play game. The following roles are available:
    {participant_roles(agents)}.
    Read the following conversation.
    Then select the next role from {[agent.name for agent in agents]} to play. The role can be selected repeatedly.Only return the role."""

    async def a_select_speaker(
        self,
        last_speaker: Agent,
        selector: ConversableAgent,
        now_goal_context: str = None,
        pre_allocated: str = None,
    ):
        """Select the next speaker."""

        agents = self.agents

        if pre_allocated:
            # Preselect speakers
            logger.info(f"Preselect speakers:{pre_allocated}")
            name = pre_allocated
            model = None
        else:
            # auto speaker selection
            selector.update_system_message(self.select_speaker_msg(agents))
            final, name, model = await selector.a_reasoning_reply(
                self.messages
                + [
                    {
                        "role": ModelMessageRoleType.HUMAN,
                        "content": f"""Read and understand the following task content and assign the appropriate role to complete the task.
                                    Task content: {now_goal_context}
                                    select the role from: {[agent.name for agent in agents]},
                                    Please only return the role, such as: {agents[0].name}""",
                    }
                ]
            )
            if not final:
                raise ValueError("Unable to select next speaker!")

        # If exactly one agent is mentioned, use it. Otherwise, leave the OAI response unmodified
        mentions = mentioned_agents(name, agents)
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
            logger.exception(f"auto select speaker failed!{str(e)}")
            raise ValueError("Unable to select next speaker!")

    async def a_generate_speech_process(
        self,
        message: Optional[str],
        reviewer: Agent,
        agents: Optional[List[Agent]] = None,
    ) -> None:
        planner = PlannerAgent(
            agent_context=self.agent_context,
            memory=self.memory,
            agents=agents,
            is_terminal_agent=True,
        )

        await self.a_initiate_chat(
            message=message, recipient=planner, reviewer=reviewer
        )

    async def a_run_chat(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Agent = None,
        config: Optional[Any] = None,
    ):
        """Run a team chat asynchronously."""

        speaker = sender

        for i in range(self.max_round):
            plans = self.memory.plans_memory.get_by_conv_id(self.agent_context.conv_id)
            if not plans or len(plans) <= 0:
                ###Have no plan, generate a new plan
                await self.a_generate_speech_process(message, reviewer, self.agents)
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
                        speaker, model = await self.a_select_speaker(
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
