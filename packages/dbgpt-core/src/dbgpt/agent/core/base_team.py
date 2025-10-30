"""Base classes for managing a group of agents in a team chat."""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import lyricore as lc

from .. import ActionOutput
from .actor_messages import ActionRequest, ReviewRequest
from .agent import (
    ActorProxyAgent,
    AgentMessage,
    AgentMessageRequest,
    AgentReviewInfo,
    AgentStateMessage,
    AgentStateTaskResult,
)
from .base_agent import ConversableAgent
from .memory.gpts import GptsPlan
from .profile import ProfileConfig
from .schema import Status

logger = logging.getLogger(__name__)


def _content_str(content: Union[str, List, None]) -> str:
    """Convert content into a string format.

    This function processes content that may be a string, a list of mixed text and
    image URLs, or None, and converts it into a string. Text is directly appended to
    the result string, while image URLs are represented by a placeholder image token.
    If the content is None, an empty string is returned.

    Args:
        content (Union[str, List, None]): The content to be processed. Can be a
            string, a list of dictionaries representing text and image URLs, or None.

    Returns:
        str: A string representation of the input content. Image URLs are replaced with
            an image token.

    Note:
    - The function expects each dictionary in the list to have a "type" key that is
        either "text" or "image_url".
        For "text" type, the "text" key's value is appended to the result.
        For "image_url", an image token is appended.
    - This function is useful for handling content that may include both text and image
        references, especially in contexts where images need to be represented as
        placeholders.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise TypeError(f"content must be None, str, or list, but got {type(content)}")

    rst = ""
    for item in content:
        if not isinstance(item, dict):
            raise TypeError(
                "Wrong content format: every element should be dict if the content is "
                "a list."
            )
        assert "type" in item, (
            "Wrong content format. Missing 'type' key in content's dict."
        )
        if item["type"] == "text":
            rst += item["text"]
        elif item["type"] == "image_url":
            rst += "<image>"
        else:
            raise ValueError(
                f"Wrong content format: unknown type {item['type']} within the content"
            )
    return rst


class Team:
    """Team class for managing a group of agents in a team chat."""

    def __init__(
        self,
        agents: Optional[List[ActorProxyAgent]] = None,
        messages: Optional[List[Dict]] = None,
        max_round: int = 100,
        is_team: bool = True,
        **kwargs,
    ):
        """Create a new Team instance."""
        self.agents = agents or []
        self.messages = messages or []
        self.max_round = max_round
        self.is_team = is_team

    def hire(self, agents: List[ActorProxyAgent]):
        """Hire roles to cooperate."""
        self.agents.extend(agents)

    @property
    def agent_names(self) -> List[str]:
        """Return the names of the agents in the group chat."""
        return [agent.role for agent in self.agents]

    def agent_by_name(self, name: str) -> ActorProxyAgent:
        """Return the agent with a given name."""
        return self.agents[self.agent_names.index(name)]

    async def select_speaker(
        self,
        last_speaker: ActorProxyAgent,
        selector: ActorProxyAgent,
        now_goal_context: Optional[str] = None,
        pre_allocated: Optional[str] = None,
    ) -> Tuple[ActorProxyAgent, Optional[str]]:
        """Select the next speaker in the group chat."""
        raise NotImplementedError

    def reset(self):
        """Reset the group chat."""
        self.messages.clear()

    def append(self, message: Dict):
        """Append a message to the group chat.

        We cast the content to str here so that it can be managed by text-based
        model.
        """
        message["content"] = _content_str(message["content"])
        self.messages.append(message)


class ManagerAgent(ConversableAgent, Team):
    """Manager Agent class."""

    profile: ProfileConfig = ProfileConfig(
        name="ManagerAgent",
        role="TeamManager",
        goal="manage all hired intelligent agents to complete mission objectives",
        constraints=[],
        desc="manage all hired intelligent agents to complete mission objectives",
    )

    is_team: bool = True
    last_rounds: int = 100

    # The management agent does not need to retry the exception. The actual execution
    # of the agent has already been retried.
    max_retry_count: int = 1

    def __init__(self, **kwargs):
        """Create a new ManagerAgent instance."""
        ConversableAgent.__init__(self, **kwargs)
        Team.__init__(self, **kwargs)
        self.current_rounds = 0
        self.thinking_response: Optional[ReviewRequest] = None
        self._plan: Dict = {}
        self._plan_cls_role: Optional[str] = None
        self._worker_agent_to_plan: Dict[str, GptsPlan] = {}

    async def _load_thinking_messages(
        self,
        received_message: AgentMessage,
        sender: ActorProxyAgent,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: bool = False,
        current_retry_counter: Optional[int] = None,
    ) -> Tuple[List[AgentMessage], Optional[Dict], Optional[str], Optional[str]]:
        """Load messages for thinking."""
        return [AgentMessage(content=received_message.content)], None, None, None

    async def adjust_final_message(
        self,
        is_success: bool,
        reply_message: AgentMessage,
    ):
        all_messages = await self.memory.gpts_memory.get_messages(
            self.agent_context.conv_id
        )
        if self.last_rounds > 0:
            reply_message.rounds = all_messages[-1].rounds + 1
        reply_message.current_goal = self.current_goal
        return is_success, reply_message

    @lc.on(ReviewRequest)
    async def handle_review_request(self, request: ReviewRequest, ctx):
        # self_ref = lc.get_current_message_context().self_ref
        thinking_response = request.thinking_response
        reply_message = thinking_response.init_message.reply_message
        llm_reply = thinking_response.thinking_text
        approve, comments = await self.review(llm_reply, self.self_proxy())
        reply_message.review_info = AgentReviewInfo(
            approve=approve,
            comments=comments,
        )
        self.thinking_response = thinking_response
        await self._start_plan(reply_message.content, reply_message.rounds)

    async def _build_agents(self, message: AgentMessage):
        pass

    async def _start_plan(self, current_goal: str, rounds: int):
        raise NotImplementedError

    async def thinking(
        self,
        messages: List[AgentMessage],
        reply_message_id: str,
        reply_message: AgentMessage,
        sender: Optional[ActorProxyAgent] = None,
        prompt: Optional[str] = None,
        current_goal: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Think and reason about the current task goal."""
        # TeamManager, which is based on processes and plans by default, only needs to
        # ensure execution and does not require additional thinking.
        if messages is None or len(messages) <= 0:
            return None, None, None
        else:
            message = messages[-1]
            self.messages.append(message.to_llm_message())
            return message.thinking, message.content, None

    async def act(
        self,
        message: AgentMessage,
        sender: ActorProxyAgent,
        reviewer: Optional[ActorProxyAgent] = None,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        **kwargs,
    ) -> ActionOutput:
        """Nothing to do in the act phase of the management agent."""
        if not message.action_report:
            return ActionOutput(
                is_exe_success=False,
                content="The action_report cannot be empty!",
            )
        return message.action_report

    async def _complete_plan(self, action_report: Optional[ActionOutput] = None):
        """Complete the task plan."""
        self_ref = lc.get_current_message_context().self_ref
        thinking_response = self.thinking_response
        reply_message = thinking_response.init_message.reply_message
        reply_message.action_report = action_report
        action_request = ActionRequest(thinking_response=thinking_response)
        # To next step, let the manager agent handle the action request.
        await self_ref.tell(action_request)

    @lc.on(AgentStateTaskResult)
    async def handle_agent_state_message(self, state: AgentStateTaskResult, ctx):
        if not isinstance(state, AgentStateTaskResult):
            # Ignore non-task-result state messages
            return
        self.current_rounds = max(self.current_rounds, state.rounds)
        if state.role == self._plan_cls_role:
            if not state.is_success:
                err_msg = f"Planning agent reported failure: {state.result if state.result else ''}"
                logger.error(err_msg)
                action_report = ActionOutput(
                    is_exe_success=False,
                    content=err_msg,
                )
                await self._complete_plan(action_report)
                return
            else:
                plans = await self.memory.gpts_memory.get_by_conv_id(
                    self.not_null_agent_context.conv_id
                )
                task_num_to_plan = {plan.sub_task_num: plan for plan in plans}
                plan_dependencies: Dict[int, List[int]] = {}
                for plan in plans:
                    sub_task_num = plan.sub_task_num
                    rely_tasks_list = plan.rely.split(",")
                    rely_tasks_list_int = [
                        int(i) for i in rely_tasks_list if i.strip() != ""
                    ]
                    plan_dependencies[sub_task_num] = rely_tasks_list_int

                self._plan = {
                    "plans": task_num_to_plan,
                    "dependencies": plan_dependencies,
                    "status": {plan.sub_task_num: plan.state for plan in plans},
                }
                await self._start_ready_tasks()
                return

        # Handle task result messages from worker agents
        action_report, final_message = await self._handle_task_result(state)
        if action_report:
            await self._complete_plan(action_report)
            return

        need_adjustment = await self._check_plan_adjustment_need(state)
        if not need_adjustment:
            # No need to adjust the plan
            if state.is_success:
                to_run_tasks = await self._start_ready_tasks()
                if to_run_tasks > 0:
                    logger.info(f"Started {to_run_tasks} ready tasks.")
                else:
                    logger.info("No ready tasks to start.")
                    action_report = ActionOutput(
                        is_exe_success=True,
                        content=final_message,
                    )
                    await self._complete_plan(action_report)
            else:
                logger.error(
                    f"Task {state.name} failed: {state.result if state.result else ''}"
                )
                action_report = ActionOutput(
                    is_exe_success=False,
                    content=state.result if state.result else "",
                )
                await self._complete_plan(action_report)
        else:
            # Plan adjustment needed (not implemented)
            logger.warning("Plan adjustment needed but not implemented.")
            action_report = ActionOutput(
                is_exe_success=False,
                content="Plan adjustment needed but not implemented.",
            )
            await self._complete_plan(action_report)

    async def _handle_task_result(self, state: AgentStateTaskResult):
        task_uniq_key = self.get_worker_agent_key(state.role, state.name)
        plan = self._worker_agent_to_plan.get(task_uniq_key, None)
        final_message = None
        if not plan:
            logger.error(f"Cannot find the plan for agent {task_uniq_key}")
            return ActionOutput(
                is_exe_success=False,
                content=f"Cannot find the plan for agent {task_uniq_key}",
            ), None
        final_message = state.result
        if state.is_success:
            action_report = state.action_report
            if action_report:
                plan_result = action_report.content
                final_message = action_report.view or action_report.content
            # TODO: run update_task in a separate thread to avoid blocking
            await self.memory.gpts_memory.complete_task(
                self.not_null_agent_context.conv_id,
                plan.task_uid,
                plan_result,
            )
            plan.state = Status.COMPLETE.value
            return None, final_message
        else:
            plan_result = state.result
            # TODO: run update_task in a separate thread to avoid blocking
            await self.memory.gpts_memory.update_task(
                self.not_null_agent_context.conv_id,
                plan.sub_task_num,
                Status.FAILED.value,
                plan.retry_times + 1,
                state.name,
                "",
                plan_result,
            )
            plan.state = Status.FAILED.value
            return ActionOutput(
                is_exe_success=False, content=plan_result
            ), final_message

    async def _start_ready_tasks(self):
        ready_tasks = []
        for task_num, plan in self._plan["plans"].items():
            if plan.state in [Status.TODO.value, Status.RETRYING.value]:
                dependencies = self._plan["dependencies"].get(task_num, [])
                if all(
                    self._plan["plans"][dep].state == Status.COMPLETE.value
                    for dep in dependencies
                ):
                    ready_tasks.append(plan)
        # Start all ready tasks concurrently
        for plan in ready_tasks:
            await self._start_task(plan, self.current_rounds)
        return len(ready_tasks)

    async def _check_plan_adjustment_need(self, state: AgentStateMessage) -> bool:
        return False

    def get_worker_agent_key(self, role: str, name: str) -> str:
        return f"{role}___$$$___{name}"

    async def _start_task(self, plan: GptsPlan, rounds: int):
        current_goal_message = AgentMessage(
            content=plan.sub_task_content,
            current_goal=plan.sub_task_content,
            context={
                "plan_task": plan.sub_task_content,
                "plan_task_num": plan.sub_task_num,
            },
            rounds=rounds + 1,
        )
        # select the next speaker
        last_speaker = None
        speaker, model = await self.select_speaker(
            last_speaker,
            self.self_proxy(),
            plan.sub_task_content,
            plan.sub_task_agent,
        )
        task_uniq_key = self.get_worker_agent_key(speaker.role, speaker.name)
        self._worker_agent_to_plan[task_uniq_key] = plan

        # Tell the speaker the dependent history information
        rely_prompt, rely_messages = await self.process_rely_message(
            conv_id=self.not_null_agent_context.conv_id,
            now_plan=plan,
        )
        if rely_prompt:
            current_goal_message.content = rely_prompt + current_goal_message.content
        req = AgentMessageRequest(
            message=current_goal_message,
            sender=self.self_proxy(),
            # reviewer=reviewer,
            rely_messages=AgentMessage.from_messages(rely_messages),
        )
        # monitor_ref = await actor_ctx.spawn(AgentStateMonitorActor, f"_agent_state_actor_{self.not_null_agent_context.conv_id}_{plan.sub_task_num}")
        await speaker.subscribe(self.self_proxy())
        # await speaker.subscribe.tell(monitor_ref)
        await speaker.tell_request(req)
        plan.state = Status.RUNNING.value
