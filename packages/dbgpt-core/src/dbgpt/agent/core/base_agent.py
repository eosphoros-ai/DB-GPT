"""Base agent class for conversable agents."""

import asyncio
import json
import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, final

import lyricore as lc
from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment

from dbgpt.core import LLMClient, ModelMessageRoleType, PromptTemplate
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import SpanType, root_tracer
from dbgpt.util.utils import colored

from ...util.annotations import Deprecated
from ..resource.base import Resource
from ..util.conv_utils import parse_conv_id
from ..util.llm.llm import LLMConfig, LLMStrategyType
from ..util.llm.llm_client import AIWrapper
from .action.base import Action, ActionOutput
from .actor_messages import (
    ActionRequest,
    AgentLoopInitMessage,
    ReviewRequest,
    ThinkingRequest,
    ThinkingResponse,
)
from .agent import (
    ActorProxyAgent,
    Agent,
    AgentContext,
    AgentMessage,
    AgentMessageRequest,
    AgentReviewInfo,
    AgentState,
    AgentStateActing,
    AgentStateIdleMessage,
    AgentStateMessage,
    AgentStateTaskResult,
    AgentStateThinking,
)
from .memory.agent_memory import AgentMemory
from .memory.gpts.base import GptsMessage
from .memory.gpts.gpts_memory import GptsMemory
from .profile.base import ProfileConfig
from .role import AgentRunMode, ConversableAgentMeta, Role

logger = logging.getLogger(__name__)


class ConversableAgent(Role, Agent, metaclass=ConversableAgentMeta):
    """ConversableAgent is an agent that can communicate with other agents."""

    def __init__(
        self,
        profile: ProfileConfig,
        memory: AgentMemory,
        fixed_subgoal: Optional[str] = None,
        language: str = "en",
        is_human: bool = False,
        is_team: bool = False,
        template_env: Optional[SandboxedEnvironment] = None,
        # Role parameters end
        agent_context: Optional[AgentContext] = None,
        actions: Optional[List[Action]] = None,
        resource: Optional[Resource] = None,
        resource_factory: Optional[Callable[[], Resource]] = None,
        llm_config: Optional[LLMConfig] = None,
        bind_prompt: Optional[PromptTemplate] = None,
        run_mode: Optional[AgentRunMode] = None,
        max_retry_count: int = 3,
        max_timeout: int = 600,
        llm_client: Optional[AIWrapper] = None,
        stream_out: bool = True,
        show_reference: bool = False,
        executor: Optional[Executor] = None,
        is_final_role: bool = False,
        show_message: bool = True,
        current_goal: Optional[str] = None,
        state_queue: Optional[lc.Queue] = None,  # Distributed state reporting queue
        **kwargs,
    ):
        Role.__init__(
            self,
            profile=profile,
            memory=memory,
            fixed_subgoal=fixed_subgoal,
            language=language,
            is_human=is_human,
            is_team=is_team,
            template_env=template_env,
        )
        Agent.__init__(self)
        self.agent_context = agent_context
        self.actions = actions or []
        self.resource = resource
        self.resource_factory = resource_factory
        self.llm_config = llm_config
        self.bind_prompt = bind_prompt
        self.run_mode = run_mode
        self.max_retry_count = max_retry_count
        self.max_timeout = max_timeout
        self.llm_client = llm_client
        self.stream_out = stream_out
        self.show_reference = show_reference
        self.executor = executor or ThreadPoolExecutor(max_workers=1)
        self.is_final_role = is_final_role
        self.show_message = show_message
        self.current_goal = current_goal
        self.state_queue = state_queue
        self._eventbus = None

    def check_available(self) -> None:
        """Check if the agent is available.

        Raises:
            ValueError: If the agent is not available.
        """
        self.identity_check()
        # check run context
        if self.agent_context is None:
            raise ValueError(
                f"{self.name}[{self.role}] Missing context in which agent is running!"
            )

        # action check
        if self.actions and len(self.actions) > 0:
            for action in self.actions:
                if action.resource_need and (
                    not self.resource
                    or not self.resource.get_resource_by_type(action.resource_need)
                ):
                    raise ValueError(
                        f"{self.name}[{self.role}] Missing resources"
                        f"[{action.resource_need}] required for runtime！"
                    )
        else:
            if not self.is_human and not self.is_team:
                raise ValueError(
                    f"This agent {self.name}[{self.role}] is missing action modules."
                )
        # llm check
        if not self.is_human and (
            self.llm_config is None or self.llm_config.llm_client is None
        ):
            raise ValueError(
                f"{self.name}[{self.role}] Model configuration is missing or model "
                "service is unavailable！"
            )

    @property
    def not_null_agent_context(self) -> AgentContext:
        """Get the agent context.

        Returns:
            AgentContext: The agent context.

        Raises:
            ValueError: If the agent context is not initialized.
        """
        if not self.agent_context:
            raise ValueError("Agent context is not initialized！")
        return self.agent_context

    @property
    def not_null_llm_config(self) -> LLMConfig:
        """Get the LLM config."""
        if not self.llm_config:
            raise ValueError("LLM config is not initialized！")
        return self.llm_config

    @property
    def not_null_llm_client(self) -> LLMClient:
        """Get the LLM client."""
        llm_client = self.not_null_llm_config.llm_client
        if not llm_client:
            raise ValueError("LLM client is not initialized！")
        return llm_client

    async def blocking_func_to_async(
        self, func: Callable[..., Any], *args, **kwargs
    ) -> Any:
        """Run a potentially blocking function within an executor."""
        if not asyncio.iscoroutinefunction(func):
            return await blocking_func_to_async(self.executor, func, *args, **kwargs)
        return await func(*args, **kwargs)

    async def preload_resource(self) -> None:
        """Preload resources before agent initialization."""
        if self.resource:
            await self.resource.preload_resource()

    async def on_start(self, ctx):
        try:
            await self.build()
            await self.report_state(
                AgentStateIdleMessage(name=self.name, role=self.role)
            )
        except Exception as e:
            logger.error(f"Agent {self.name} failed to build: {e}")
            raise e

    async def subscribe(self, ref, topic: Optional[str] = "agent.state"):
        """Subscribe to a topic."""
        if not self._eventbus:
            logger.warning("Event bus is not initialized!")
            raise ValueError("Event bus is not initialized!")
        try:
            await self._eventbus.subscribe(ref, topic)
            stats = await self._eventbus.get_stats()
            logger.debug(f"Subscribed to topic {topic}, eventbus stats: {stats}")
        except Exception as e:
            logger.error(f"Failed to subscribe to topic {topic}: {e}")

    async def report_state(self, state_message: AgentStateMessage):
        """Report the state of the agent."""
        if self.state_queue:
            await self.state_queue.put(state_message)
        else:
            logger.warning("State queue is not initialized!")
        if self._eventbus:
            await self._eventbus.publish(state_message, topic="agent.state")

    async def _build_factory(self):
        if not self.resource and self.resource_factory:
            self.resource = self.resource_factory()

    async def build(self, is_retry_chat: bool = False) -> "ConversableAgent":
        """Build the agent."""
        await self._build_factory()
        # Preload resources
        await self.preload_resource()
        # Check if agent is available
        self.check_available()
        _language = self.not_null_agent_context.language
        if _language:
            self.language = _language

        # Initialize resource loader
        for action in self.actions:
            action.init_resource(self.resource)

        # Initialize LLM Server
        if not self.is_human:
            if not self.llm_config or not self.llm_config.llm_client:
                raise ValueError("LLM client is not initialized！")
            self.llm_client = AIWrapper(llm_client=self.llm_config.llm_client)
            real_conv_id, _ = parse_conv_id(self.not_null_agent_context.conv_id)
            memory_session = f"{real_conv_id}_{self.role}_{self.name}"
            await self.memory.initialize(
                self.name,
                self.llm_config.llm_client,
                importance_scorer=self.memory_importance_scorer,
                insight_extractor=self.memory_insight_extractor,
                session_id=memory_session,
            )
            # Clone the memory structure
            self.memory = self.memory.structure_clone()
            action_outputs = await self.memory.gpts_memory.get_agent_history_memory(
                real_conv_id, self.role
            )
            await self.recovering_memory(action_outputs)

        self.profile = deepcopy(self.profile)
        for action in self.actions:
            action.init_action(
                language=self.language,
                render_protocol=self.memory.gpts_memory.vis_converter,
            )
        if not self._eventbus:
            self._eventbus = lc.EventBus()
        return self

    def bind(self, target: Any) -> "ConversableAgent":
        """Bind the resources to the agent."""
        if isinstance(target, LLMConfig):
            self.llm_config = target
        elif isinstance(target, GptsMemory):
            raise ValueError("GptsMemory is not supported!Please Use Agent Memory")
        elif isinstance(target, AgentContext):
            self.agent_context = target
        elif isinstance(target, Resource):
            self.resource = target
        elif isinstance(target, AgentMemory):
            self.memory = target
        elif isinstance(target, ProfileConfig):
            self.profile = target
        elif isinstance(target, type) and issubclass(target, Action):
            self.actions.append(target())
        elif isinstance(target, Action):
            self.actions.append(target)
        elif isinstance(target, list) and all(
            [isinstance(item, type) and issubclass(item, Action) for item in target]
        ):
            for action in target:
                self.actions.append(action())
        elif isinstance(target, list) and all(
            [isinstance(item, Action) for item in target]
        ):
            self.actions.extend(target)
        elif isinstance(target, PromptTemplate):
            self.bind_prompt = target

        return self

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: ActorProxyAgent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare the parameters for the act method."""
        return {}

    @final
    async def generate_reply(self, request: AgentMessageRequest):
        self_ref = lc.get_current_message_context().self_ref
        received_message = request.message
        sender = request.sender
        reviewer = request.reviewer
        rely_messages = request.rely_messages
        historical_dialogues = request.historical_dialogues
        is_retry_chat = request.is_retry_chat
        current_retry_counter = request.current_retry_counter
        reply_message = await self.init_reply_message(
            received_message=received_message, sender=sender
        )
        (
            thinking_messages,
            resource_info,
            system_prompt,
            user_prompt,
        ) = await self._load_thinking_messages(
            received_message=received_message,
            sender=sender,
            rely_messages=rely_messages,
            historical_dialogues=historical_dialogues,
            context=reply_message.get_dict_context(),
            is_retry_chat=is_retry_chat,
            current_retry_counter=current_retry_counter,
        )
        init_message = AgentLoopInitMessage(
            request=request,
            reply_message=reply_message,
            sender=sender,
            thinking_messages=thinking_messages,
            received_message=received_message,
            current_retry_counter=current_retry_counter,
            resource_references=resource_info,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            historical_dialogues=historical_dialogues,
        )
        thinking_request = ThinkingRequest(
            init_message=init_message,
            current_goal=received_message.current_goal or self.current_goal,
        )
        # Send to self for processing
        await self_ref.tell(thinking_request)

    @lc.on(ThinkingRequest)
    async def handle_thinking_request(self, request: ThinkingRequest, ctx):
        self_ref = lc.get_current_message_context().self_ref

        thinking_messages = request.init_message.thinking_messages
        current_retry_counter = request.init_message.current_retry_counter
        reply_message = request.init_message.reply_message
        sender = request.init_message.sender
        current_goal = request.current_goal
        resource_info = request.init_message.resource_references

        # Report thinking state
        await self.report_state(
            AgentStateThinking(
                name=self.name,
                role=self.role,
                current_retry_counter=current_retry_counter,
                conv_id=self.not_null_agent_context.conv_id,
            )
        )

        llm_thinking, llm_content, model_name = await self.thinking(
            thinking_messages,
            reply_message.message_id,
            reply_message,
            sender,
            current_goal=current_goal,
        )
        # Some models may not return content but only thinking
        llm_content = llm_content or llm_thinking
        reply_message.model_name = model_name
        reply_message.thinking = llm_thinking
        reply_message.content = llm_content
        reply_message.resource_info = resource_info
        thinking_response = ThinkingResponse(
            init_message=request.init_message,
            model_name=model_name,
            text=llm_content,
            thinking_text=llm_thinking,
        )
        review_request = ReviewRequest(thinking_response=thinking_response)
        await self_ref.tell(review_request)

    @lc.on(ReviewRequest)
    async def handle_review_request(self, request: ReviewRequest, ctx):
        self_ref = lc.get_current_message_context().self_ref
        thinking_response = request.thinking_response
        reply_message = thinking_response.init_message.reply_message
        llm_reply = thinking_response.thinking_text
        approve, comments = await self.review(llm_reply, self.self_proxy())
        reply_message.review_info = AgentReviewInfo(
            approve=approve,
            comments=comments,
        )
        action_request = ActionRequest(thinking_response=thinking_response)
        await self_ref.tell(action_request)

    @lc.on(ActionRequest)
    async def handle_action_request(self, request: ActionRequest, ctx):
        # TODO: Handle exceptions in each step
        self_ref = self.self_proxy()
        init_message = request.thinking_response.init_message
        sender: ActorProxyAgent = init_message.sender
        reviewer = init_message.reviewer
        thinking_response = request.thinking_response
        reply_message = init_message.reply_message
        received_message = init_message.received_message
        historical_dialogues = init_message.historical_dialogues

        act_extent_param = self.prepare_act_param(
            received_message=received_message,
            sender=sender,
            rely_messages=None,  # No rely messages in this flow
            historical_dialogues=historical_dialogues,
            reply_message=reply_message,
        )

        await self.report_state(
            AgentStateActing(
                name=self.name,
                role=self.role,
                current_retry_counter=init_message.current_retry_counter,
                conv_id=self.not_null_agent_context.conv_id,
            )
        )

        act_out: ActionOutput = await self.act(
            message=reply_message,
            sender=sender,
            reviewer=None,
            is_retry_chat=False,
            last_speaker_name=None,
            **act_extent_param,
        )
        if act_out:
            reply_message.action_report = act_out

        check_pass, reason = await self.verify(reply_message, sender, reviewer=reviewer)
        is_success = check_pass

        question: str = init_message.observation or received_message.content or ""
        ai_message: str = thinking_response.text
        # 5.Optimize wrong answers myself
        break_loop = False
        current_retry_counter = init_message.current_retry_counter
        if not check_pass:
            if not act_out.have_retry:
                logger.warning("No retry available!")
                break_loop = True
            fail_reason = reason
            latest_observation = fail_reason
            await self.write_memories(
                question=question,
                ai_message=ai_message,
                action_output=act_out,
                check_pass=check_pass,
                check_fail_reason=fail_reason,
                current_retry_counter=current_retry_counter,
            )
        else:
            # Successful reply
            latest_observation = act_out.observations
            await self.write_memories(
                question=question,
                ai_message=ai_message,
                action_output=act_out,
                check_pass=check_pass,
                current_retry_counter=current_retry_counter,
            )
            if self.run_mode != AgentRunMode.LOOP or act_out.terminate:
                logger.debug(f"Agent {self.name} reply success!{reply_message}")
                break_loop = True
        if not break_loop:
            # Continue to run the next round
            init_message.observation = latest_observation
            init_message.reply_message.content = latest_observation
            init_message.current_retry_counter += 1

            retry_message = AgentMessage.init_new(
                content=latest_observation,
                current_goal=received_message.current_goal or self.current_goal,
                rounds=reply_message.rounds + 1,
            )
            # The current message is a self-optimized message that needs to be
            # recorded.
            # It is temporarily set to be initiated by the originating end to
            # facilitate the organization of historical memory context.
            await self_ref.tell(
                retry_message,
                reviewer=reviewer,
                request_reply=False,
                sender_agent=sender,
            )
            received_message.rounds = retry_message.rounds + 1

        reply_message.success = is_success
        # if init_message.current_retry_counter < self.max_retry_count:
        # Send current reply message to sender
        await sender.tell(
            reply_message,
            reviewer=reviewer,
            request_reply=False,
            sender_agent=self_ref,
        )
        await self.adjust_final_message(is_success, reply_message)

        if not break_loop:
            # Send to self for next thinking
            init_message.reply_message.rounds += 1
            await self_ref.tell(
                init_message.reply_message,
                reviewer=reviewer,
                sender=sender,
                sender_agent=sender,
                current_retry_counter=init_message.current_retry_counter,
            )
        else:
            # TODO: Find a better way to end the loop
            action_report = reply_message.action_report
            if is_success:
                state = AgentState.TASK_SUCCEEDED
                result = (
                    reply_message.action_report
                    if reply_message.action_report
                    else reply_message.content
                )
            else:
                state = AgentState.TASK_FAILED
                result = reason or reply_message.content
            await self.report_state(
                AgentStateTaskResult(
                    name=self.name,
                    role=self.role,
                    state=state,
                    conv_id=self.not_null_agent_context.conv_id,
                    result=result,
                    action_report=action_report,
                    rounds=reply_message.rounds,
                    current_retry_counter=current_retry_counter,
                )
            )
            # Can't complete if multiple agents are involved
            # await self.memory.gpts_memory.complete(self.not_null_agent_context.conv_id)
            logger.info(f"Agent {self.name} finished the conversation loop.")

    async def thinking(
        self,
        messages: List[AgentMessage],
        reply_message_id: str,
        reply_message: AgentMessage,
        sender: Optional[ActorProxyAgent] = None,
        prompt: Optional[str] = None,
        current_goal: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Think and reason about the current task goal.

        Args:
            messages(List[AgentMessage]): the messages to be reasoned
            prompt(str): the prompt to be reasoned
        """
        last_model = None
        last_err = None
        retry_count = 0
        llm_messages = [message.to_llm_message() for message in messages]
        # LLM inference automatically retries 3 times to reduce interruption
        # probability caused by speed limit and network stability
        while retry_count < 3:
            llm_model = await self._a_select_llm_model(last_model)
            try:
                logger.info(f"model:{llm_model} chat begin!retry_count:{retry_count}")
                if prompt:
                    llm_messages = _new_system_message(prompt) + llm_messages

                if not self.llm_client:
                    raise ValueError("LLM client is not initialized!")

                prev_thinking = ""
                prev_content = ""
                is_first_chunk = True
                async for output in self.llm_client.create(
                    context=llm_messages[-1].pop("context", None),
                    messages=llm_messages,
                    llm_model=llm_model,
                    max_new_tokens=self.not_null_agent_context.max_new_tokens,
                    temperature=self.not_null_agent_context.temperature,
                    verbose=self.not_null_agent_context.verbose,
                    trace_id=self.not_null_agent_context.trace_id,
                    rpc_id=self.not_null_agent_context.rpc_id,
                ):
                    current_thinking, current_content = output

                    if self.not_null_agent_context.incremental:
                        res_thinking = current_thinking[len(prev_thinking) :]
                        res_content = current_content[len(prev_content) :]
                        prev_thinking = current_thinking
                        prev_content = current_content

                    else:
                        res_thinking = current_thinking
                        res_content = current_content
                        prev_thinking = res_thinking
                        prev_content = res_content

                    if self.stream_out:
                        reply_message.model_name = llm_model
                        reply_message.thinking = res_thinking
                        reply_message.content = res_content
                        reply_message.avatar = (self.avatar,)
                        if current_goal:
                            reply_message.current_goal = current_goal

                        if not self.not_null_agent_context.output_process_message:
                            if self.is_final_role:
                                await self.memory.gpts_memory.append_message(
                                    self.agent_context.conv_id,
                                    reply_message.to_gpts_message(
                                        sender=self, role=None, receiver=None
                                    ),
                                    save_db=False,
                                )
                        else:
                            await self.memory.gpts_memory.append_message(
                                self.agent_context.conv_id,
                                reply_message.to_gpts_message(
                                    sender=self, role=None, receiver=None
                                ),
                                save_db=False,
                            )
                        if is_first_chunk:
                            is_first_chunk = False

                return prev_thinking, prev_content, llm_model
            except LLMChatError as e:
                logger.exception(f"model:{llm_model} generate Failed!{str(e)}")
                if e.original_exception and e.original_exception > 0:
                    ## TODO 可以尝试发一个系统提示消息

                    ## 模型调用返回错误码大于0，可以使用其他模型兜底重试，小于0 没必要重试直接返回异常
                    retry_count += 1
                    last_model = llm_model
                    last_err = str(e)
                    await asyncio.sleep(1)
                else:
                    raise
            except Exception:
                raise

        if last_err:
            raise ValueError(last_err)
        else:
            raise ValueError("LLM model inference failed!")

    async def review(
        self, message: Optional[str], censored: ActorProxyAgent
    ) -> Tuple[bool, Any]:
        """Review the message based on the censored message."""
        return True, None

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
                ai_message = message.content if message.content else ""
                real_action = action.parse_action(
                    ai_message, default_action=action, **kwargs
                )
                if real_action is None:
                    continue

                last_out = await real_action.run(
                    ai_message=message.content if message.content else "",
                    resource=None,
                    rely_action_out=last_out,
                    render_protocol=self.memory.gpts_memory.vis_converter,
                    message_id=message.message_id,
                    **kwargs,
                )
                if last_out.terminate:
                    break
                span.metadata["action_out"] = last_out.to_dict() if last_out else None
        if not last_out:
            raise ValueError("Action should return value！")
        return last_out

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """Verify the correctness of the results."""
        return True, None

    async def verify(
        self,
        message: AgentMessage,
        sender: ActorProxyAgent,
        reviewer: Optional[ActorProxyAgent] = None,
        **kwargs,
    ) -> Tuple[bool, Optional[str]]:
        """Verify the current execution results."""
        # Check approval results
        if message.review_info and not message.review_info.approve:
            return False, message.review_info.comments

        # Check action run results
        action_output: Optional[ActionOutput] = message.action_report
        if action_output:
            if not action_output.is_exe_success:
                return False, action_output.content
            elif not action_output.content or len(action_output.content.strip()) < 1:
                return (
                    False,
                    "The current execution result is empty. Please rethink the "
                    "question and background and generate a new answer.. ",
                )

        # agent output correctness check
        return await self.correctness_check(message)

    def self_proxy(self, with_ref: bool = True) -> ActorProxyAgent:
        """Get the self sender."""
        if with_ref:
            actor_ctx = lc.get_current_message_context()
            self_ref = actor_ctx.self_ref
        else:
            self_ref = None
        sender = ActorProxyAgent(
            agent_context=self.agent_context,
            actor_ref=self_ref,
            name=self.name,
            role=self.role,
            desc=self.desc,
            avatar=self.avatar,
        )
        return sender

    async def initiate_chat(
        self,
        recipient: ActorProxyAgent,
        reviewer: Optional[ActorProxyAgent] = None,
        message: Optional[str] = None,
        request_reply: bool = True,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        message_rounds: int = 0,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        ctx: Optional[lc.ActorContext] = None,
        **context,
    ):
        """Initiate a chat with another agent.

        Args:
            recipient (ActorProxyAgent): The recipient agent.
            reviewer (ActorProxyAgent): The reviewer agent.
            message (str): The message to send.
        """
        agent_message = AgentMessage(
            content=message,
            current_goal=message,
            rounds=message_rounds,
            context=context,
        )
        with root_tracer.start_span(
            "agent.initiate_chat",
            span_type=SpanType.AGENT,
            metadata={
                "sender": self.name,
                "recipient": recipient.name,
                "reviewer": reviewer.name if reviewer else None,
                "agent_message": json.dumps(
                    agent_message.to_dict(), ensure_ascii=False
                ),
                "conv_uid": self.not_null_agent_context.conv_id,
            },
        ):
            req = AgentMessageRequest(
                message=agent_message,
                sender=self.self_proxy(),
                reviewer=reviewer,
                request_reply=request_reply,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
                rely_messages=rely_messages,
                historical_dialogues=historical_dialogues,
            )
            res = await recipient.tell_request(req)
            return res

    @lc.on(AgentMessageRequest)
    async def handle_agent_request(self, request: AgentMessageRequest, ctx):
        message = request.message
        sender = request.sender
        request_reply = request.request_reply

        await self._a_process_received_message(message, sender)
        if not request_reply:
            return

        if not self.is_human:
            if isinstance(sender, ConversableAgent) and sender.is_human:
                pass
            else:
                request.last_speaker_name = None
            await self.generate_reply(request)

    async def adjust_final_message(
        self,
        is_success: bool,
        reply_message: AgentMessage,
    ):
        """Adjust final message after agent reply."""
        return is_success, reply_message

    #######################################################################
    # Private Function Begin
    #######################################################################

    def _init_actions(self, actions: List[Type[Action]]):
        self.actions = []
        for idx, action in enumerate(actions):
            if issubclass(action, Action):
                self.actions.append(action(language=self.language))

    async def _a_append_message(
        self,
        message: AgentMessage,
        role,
        sender: ActorProxyAgent,
        receiver: Optional[ActorProxyAgent] = None,
    ) -> bool:
        logger.info(f"_a_append_message:{message}")
        receiver_role: Optional[str] = receiver.role if receiver else None
        receiver_name: Optional[str] = receiver.name if receiver else None
        gpts_message: GptsMessage = message.to_gpts_message(
            sender=sender,
            role=role,
            receiver=receiver,
            receiver_role=receiver_role,
            receiver_name=receiver_name,
        )
        with root_tracer.start_span(
            "agent.save_message_to_memory",
            metadata={
                "gpts_message": gpts_message.to_dict(),
                "conv_uid": self.not_null_agent_context.conv_id,
            },
        ):
            await self.memory.gpts_memory.append_message(
                self.not_null_agent_context.conv_id, gpts_message
            )
            return True

    def _print_received_message(self, message: AgentMessage, sender: ActorProxyAgent):
        # print the message received
        print("\n", "-" * 80, flush=True, sep="")
        _print_name = self.name if self.name else self.role
        print(
            colored(
                sender.name if sender.name else sender.role,
                "yellow",
            ),
            "(to",
            f"{_print_name})-[{message.model_name or ''}]:\n",
            flush=True,
        )

        content = json.dumps(message.content, ensure_ascii=False)
        if content is not None:
            print(content, flush=True)

        review_info = message.review_info
        if review_info:
            name = sender.name if sender.name else sender.role
            pass_msg = "Pass" if review_info.approve else "Reject"
            review_msg = f"{pass_msg}({review_info.comments})"
            approve_print = f">>>>>>>>{name} Review info: \n{review_msg}"
            print(colored(approve_print, "green"), flush=True)

        action_report = message.action_report
        if action_report:
            name = sender.name if sender.name else sender.role
            action_msg = (
                "execution succeeded"
                if action_report.is_exe_success
                else "execution failed"
            )
            action_report_msg = f"{action_msg},\n{action_report.content}"
            action_print = f">>>>>>>>{name} Action report: \n{action_report_msg}"
            print(colored(action_print, "blue"), flush=True)

        print("\n", "-" * 80, flush=True, sep="")

    async def _a_process_received_message(
        self, message: AgentMessage, sender: ActorProxyAgent
    ):
        valid = await self._a_append_message(message, None, sender, self.self_proxy())
        if not valid:
            raise ValueError(
                "Received message can't be converted into a valid ChatCompletion"
                " message. Either content or function_call must be provided."
            )

        self._print_received_message(message, sender)

    async def load_resource(self, question: str, is_retry_chat: bool = False):
        """Load agent bind resource."""
        if self.resource:
            resource_prompt, resource_reference = await self.resource.get_prompt(
                lang=self.language, question=question
            )
            return resource_prompt, resource_reference
        return None, None

    async def agent_full_desc(self) -> str:
        """The full description of the agent.

        It will be as the description when it as a member of a team.

        If this is a tool agent, the description will include the simple tool list and
        their simple description.

        If this is an agent which has other resources, the description will include
        the simple resource list and their simple description.

        Returns:
            str: The full description of the agent.
        """
        desc = f"{self.role}:{self.desc}"
        # TODO: Add tool list and resource list
        return desc

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
            "resource_prompt": resource_prompt,
            "out_schema": out_schema,
            "now_time": now_time,
        }

    def _excluded_models(
        self,
        all_models: List[str],
        order_llms: Optional[List[str]] = None,
        excluded_models: Optional[List[str]] = None,
    ):
        if not order_llms:
            order_llms = []
        if not excluded_models:
            excluded_models = []
        can_uses = []
        if order_llms and len(order_llms) > 0:
            for llm_name in order_llms:
                if llm_name in all_models and (
                    not excluded_models or llm_name not in excluded_models
                ):
                    can_uses.append(llm_name)
        else:
            for llm_name in all_models:
                if not excluded_models or llm_name not in excluded_models:
                    can_uses.append(llm_name)

        return can_uses

    @classmethod
    def convert_to_agent_message(
        cls,
        gpts_messages: List[GptsMessage],
        is_rery_chat: bool = False,
    ) -> Optional[List[AgentMessage]]:
        """Convert gptmessage to agent message."""
        oai_messages: List[AgentMessage] = []
        # Based on the current agent, all messages received are user, and all messages
        # sent are assistant.
        if not gpts_messages:
            return None
        for item in gpts_messages:
            # Message conversion, priority is given to converting execution results,
            # and only model output results will be used if not.
            content = item.content
            oai_messages.append(
                AgentMessage(
                    message_id=item.message_id,
                    content=item.content,
                    thinking=item.thinking,
                    context=(
                        json.loads(item.context) if item.context is not None else None
                    ),
                    action_report=(
                        ActionOutput.from_dict(json.loads(item.action_report))
                        if item.action_report
                        else None
                    ),
                    name=item.sender,
                    role=item.role,
                    goal_id=item.goal_id,
                    rounds=item.rounds,
                    model_name=item.model_name,
                    success=item.is_success,
                    show_message=item.show_message,
                    system_prompt=item.system_prompt,
                    user_prompt=item.user_prompt,
                )
            )
        return oai_messages

    async def _a_select_llm_model(
        self, excluded_models: Optional[List[str]] = None
    ) -> str:
        logger.info(f"_a_select_llm_model:{excluded_models}")
        try:
            all_models = await self.not_null_llm_client.models()
            all_model_names = [item.model for item in all_models]
            # TODO Currently only two strategies, priority and default, are implemented.
            if self.not_null_llm_config.llm_strategy == LLMStrategyType.Priority:
                priority: List[str] = []
                strategy_context = self.not_null_llm_config.strategy_context
                if strategy_context is not None:
                    priority = json.loads(strategy_context)  # type: ignore
                can_uses = self._excluded_models(
                    all_model_names, priority, excluded_models
                )
            else:
                can_uses = self._excluded_models(all_model_names, None, excluded_models)
            if can_uses and len(can_uses) > 0:
                return can_uses[0]
            else:
                raise ValueError("No model service available!")
        except Exception as e:
            logger.error(f"{self.role} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")

    async def init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
        sender: Optional[ActorProxyAgent] = None,
        rounds: Optional[int] = None,
    ) -> AgentMessage:
        """Create a new message from the received message.

        Initialize a new message from the received message

        Args:
            received_message(AgentMessage): The received message
            rely_messages(List[AgentMessage], optional): The messages to rely on.
            sender(ActorProxyAgent, optional): The sender of the message.
            rounds(int, optional): The rounds of the message.

        Returns:
            AgentMessage: A new message
        """
        new_message = AgentMessage.init_new(
            content="",
            current_goal=received_message.current_goal or self.current_goal,
            goal_id=received_message.goal_id,
            context=received_message.context,
            rounds=rounds if rounds is not None else received_message.rounds + 1,
            name=self.name,
            role=self.role,
            show_message=self.show_message,
        )
        await self._a_append_message(new_message, None, self)
        return new_message

    @Deprecated(
        reason="Use `init_reply_message` instead",
        version="0.7.4",
        remove_version="0.8.0",
    )
    async def _a_init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> Optional[AgentMessage]:
        """Create a new message from the received message.

        If return not None, the `_init_reply_message` method will not be called.
        """
        return await self.init_reply_message(received_message, rely_messages)

    def _convert_to_ai_message(
        self,
        gpts_messages: List[GptsMessage],
        is_rery_chat: bool = False,
    ) -> List[AgentMessage]:
        oai_messages: List[AgentMessage] = []
        # Based on the current agent, all messages received are user, and all messages
        # sent are assistant.
        for item in gpts_messages:
            if item.role:
                role = item.role
            else:
                if item.receiver == self.role:
                    role = ModelMessageRoleType.HUMAN
                elif item.sender == self.role:
                    role = ModelMessageRoleType.AI
                else:
                    continue

            # Message conversion, priority is given to converting execution results,
            # and only model output results will be used if not.
            content = item.content
            if item.action_report:
                action_out = ActionOutput.from_dict(json.loads(item.action_report))
                if is_rery_chat:
                    if action_out is not None and action_out.content:
                        content = action_out.content
                else:
                    if (
                        action_out is not None
                        and action_out.is_exe_success
                        and action_out.content is not None
                    ):
                        content = action_out.content
            oai_messages.append(
                AgentMessage(
                    content=content,
                    role=role,
                    context=(
                        json.loads(item.context) if item.context is not None else None
                    ),
                )
            )
        return oai_messages

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
        question = received_message.content
        observation = question
        if not question:
            raise ValueError("The received message content is empty!")
        most_recent_memories = ""
        memory_list = []
        # Read the memories according to the current observation
        memories = await self.read_memories(observation)
        if isinstance(memories, list):
            memory_list = memories
        else:
            most_recent_memories = memories
        has_memories = True if memories else False
        reply_message_str = ""
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
            most_recent_memories += "\n" + reply_message_str
        try:
            # Load the resource prompt according to the current observation
            resource_prompt_str, resource_references = await self.load_resource(
                observation, is_retry_chat=is_retry_chat
            )
        except Exception as e:
            logger.exception(f"Load resource error！{str(e)}")
            raise ValueError(f"Load resource error！{str(e)}")

        resource_vars = await self.generate_resource_variables(resource_prompt_str)

        system_prompt = await self.build_system_prompt(
            question=question,
            most_recent_memories=most_recent_memories,
            resource_vars=resource_vars,
            context=context,
            is_retry_chat=is_retry_chat,
        )
        user_prompt = await self.build_prompt(
            question=question,
            is_system=False,
            most_recent_memories=most_recent_memories,
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
        if not user_prompt and (not memory_list or not current_retry_counter):
            # The user prompt is empty, and the current retry count is 0 or the memory
            # is empty
            user_prompt = f"Observation: {observation}"
        if user_prompt:
            agent_messages.append(
                AgentMessage(
                    content=user_prompt,
                    role=ModelMessageRoleType.HUMAN,
                )
            )
        return agent_messages, resource_references, system_prompt, user_prompt


def _new_system_message(content):
    """Return the system message."""
    return [{"content": content, "role": ModelMessageRoleType.SYSTEM}]


def _is_list_of_type(lst: List[Any], type_cls: type) -> bool:
    return all(isinstance(item, type_cls) for item in lst)
