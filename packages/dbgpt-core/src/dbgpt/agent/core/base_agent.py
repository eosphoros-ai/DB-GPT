"""Base agent class for conversable agents."""

from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, final

from jinja2 import Template

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import LLMClient, ModelMessageRoleType, PromptTemplate
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import SpanType, root_tracer
from dbgpt.util.utils import colored

from ..resource.base import Resource
from ..util.conv_utils import parse_conv_id
from ..util.llm.llm_client import AIWrapper
from ..util.llm.strategy.base import LLMConfig
from ..util.llm.strategy_manage import get_llm_strategy_manager
from .action.base import Action, ActionOutput
from .agent import Agent, AgentContext, AgentMessage, AgentReviewInfo
from .memory.agent_memory import AgentMemory
from .memory.gpts.base import GptsMessage
from .memory.gpts.gpts_memory import GptsMemory
from .profile.base import ProfileConfig
from .role import AgentRunMode, Role

logger = logging.getLogger(__name__)


class ConversableAgent(Role, Agent):
    """ConversableAgent is an agent that can communicate with other agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_context: Optional[AgentContext] = Field(None, description="Agent context")
    actions: List[Action] = Field(default_factory=list)
    resource: Optional[Resource] = Field(None, description="Resource")
    llm_config: Optional[LLMConfig] = None
    bind_prompt: Optional[PromptTemplate] = None
    run_mode: Optional[AgentRunMode] = Field(default=None, description="Run mode")
    max_retry_count: int = 3
    current_retry_counter: int = 0
    llm_client: Optional[AIWrapper] = None
    # 确认当前Agent是否需要进行流式输出
    stream_out: bool = True
    # 确认当前Agent是否需要进行参考资源展示
    show_reference: bool = False

    # 最后的发言角色
    is_final_role: bool = False

    # 当前Agent消息是否显示
    show_message: bool = True

    executor: Executor = Field(
        default_factory=lambda: ThreadPoolExecutor(max_workers=1),
        description="Executor for running tasks",
    )

    def __init__(self, **kwargs):
        """Create a new agent."""
        Role.__init__(self, **kwargs)
        Agent.__init__(self)

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
        # # llm check
        # if not self.is_human and (
        #     self.llm_config is None or self.llm_config.llm_client is None
        # ):
        #     raise ValueError(
        #         f"{self.name}[{self.role}] Model configuration is missing or model "
        #         "service is unavailable！"
        #     )

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
            await self.blocking_func_to_async(self.resource.preload_resource)

    async def build(self) -> "ConversableAgent":
        """Build the agent."""
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
        if self.llm_config and self.llm_config.llm_client:
            self.llm_client = AIWrapper(llm_client=self.llm_config.llm_client)
        if not self.is_human:
            real_conv_id, _ = parse_conv_id(self.not_null_agent_context.conv_id)
            memory_session = f"{real_conv_id}_{self.role}_{self.name}"
            self.memory.initialize(
                self.name,
                self.llm_config.llm_client
                if self.llm_config and self.llm_config.llm_client
                else None,
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

        temp_profile = self.profile
        from copy import deepcopy

        self.profile = deepcopy(temp_profile)
        for action in self.actions:
            action.init_action(
                language=self.language,
                render_protocol=self.memory.gpts_memory.vis_converter(
                    self.not_null_agent_context.conv_id
                ),
            )
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

    async def send(
        self,
        message: AgentMessage,
        recipient: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
        silent: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
    ) -> None:
        """Send a message to recipient agent."""
        with root_tracer.start_span(
            "agent.send",
            metadata={
                "sender": self.name,
                "recipient": recipient.name,
                "reviewer": reviewer.name if reviewer else None,
                "agent_message": json.dumps(message.to_dict(), ensure_ascii=False),
                "request_reply": request_reply,
                "is_recovery": is_recovery,
                "conv_uid": self.not_null_agent_context.conv_id,
            },
        ):
            await recipient.receive(
                message=message,
                sender=self,
                reviewer=reviewer,
                request_reply=request_reply,
                is_recovery=is_recovery,
                silent=silent,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
                historical_dialogues=historical_dialogues,
                rely_messages=rely_messages,
            )

    async def receive(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> None:
        """Receive a message from another agent."""
        with root_tracer.start_span(
            "agent.receive",
            metadata={
                "sender": sender.name,
                "recipient": self.name,
                "reviewer": reviewer.name if reviewer else None,
                "agent_message": json.dumps(message.to_dict(), ensure_ascii=False),
                "request_reply": request_reply,
                "silent": silent,
                "is_recovery": is_recovery,
                "conv_uid": self.not_null_agent_context.conv_id,
                "is_human": self.is_human,
            },
        ):
            await self._a_process_received_message(message, sender)
            if request_reply is False or request_reply is None:
                return

            if not self.is_human:
                if isinstance(sender, ConversableAgent) and sender.is_human:
                    reply = await self.generate_reply(
                        received_message=message,
                        sender=sender,
                        reviewer=reviewer,
                        is_retry_chat=is_retry_chat,
                        last_speaker_name=last_speaker_name,
                        historical_dialogues=historical_dialogues,
                        rely_messages=rely_messages,
                    )
                else:
                    reply = await self.generate_reply(
                        received_message=message,
                        sender=sender,
                        reviewer=reviewer,
                        is_retry_chat=is_retry_chat,
                        historical_dialogues=historical_dialogues,
                        rely_messages=rely_messages,
                    )

                if reply is not None:
                    await self.send(reply, sender)

    def prepare_act_param(
        self,
        received_message: Optional[AgentMessage],
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Prepare the parameters for the act method."""
        return {}

    @final
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
        logger.info(
            f"generate agent reply!sender={sender}, rely_messages_len={rely_messages}"
        )
        root_span = root_tracer.start_span(
            "agent.generate_reply",
            metadata={
                "sender": sender.name,
                "recipient": self.name,
                "reviewer": reviewer.name if reviewer else None,
                "received_message": json.dumps(received_message.to_dict()),
                "conv_uid": self.not_null_agent_context.conv_id,
                "rely_messages": (
                    [msg.to_dict() for msg in rely_messages] if rely_messages else None
                ),
            },
        )
        reply_message = None

        try:
            fail_reason = None
            self.current_retry_counter = 0
            is_success = True
            done = False
            observation = received_message.content or ""
            while not done and self.current_retry_counter < self.max_retry_count:
                if self.current_retry_counter > 0:
                    retry_message = AgentMessage.init_new(
                        content=fail_reason or observation,
                        current_goal=received_message.current_goal,
                        rounds=reply_message.rounds + 1,
                    )

                    # The current message is a self-optimized message that needs to be
                    # recorded.
                    # It is temporarily set to be initiated by the originating end to
                    # facilitate the organization of historical memory context.
                    await sender.send(
                        retry_message, self, reviewer, request_reply=False
                    )
                    received_message.rounds = retry_message.rounds + 1

                with root_tracer.start_span(
                    "agent.generate_reply.init_reply_message",
                ) as span:
                    # initialize reply message
                    a_reply_message: Optional[
                        AgentMessage
                    ] = await self._a_init_reply_message(
                        received_message=received_message
                    )
                    if a_reply_message:
                        reply_message = a_reply_message
                    else:
                        reply_message = await self.init_reply_message(
                            received_message=received_message, sender=sender
                        )
                    span.metadata["reply_message"] = reply_message.to_dict()

                # In manual retry mode, load all messages of the last speaker as dependent messages # noqa
                logger.info(
                    f"Depends on the number of historical messages:{len(rely_messages) if rely_messages else 0}！"  # noqa: E501
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
                    force_use_historical=kwargs.get("force_use_historical"),
                )
                reply_message.system_prompt = system_prompt
                reply_message.user_prompt = user_prompt
                with root_tracer.start_span(
                    "agent.generate_reply.thinking",
                    metadata={
                        "thinking_messages": json.dumps(
                            [msg.to_dict() for msg in thinking_messages],
                            ensure_ascii=False,
                        )
                    },
                ) as span:
                    # 1.Think about how to do things
                    llm_thinking, llm_content, model_name = await self.thinking(
                        thinking_messages, reply_message.message_id, sender
                    )

                    reply_message.model_name = model_name
                    reply_message.content = llm_content
                    reply_message.thinking = llm_thinking
                    reply_message.resource_info = resource_info
                    span.metadata["llm_reply"] = llm_content
                    span.metadata["model_name"] = model_name

                with root_tracer.start_span(
                    "agent.generate_reply.review",
                    metadata={"llm_reply": llm_content, "censored": self.name},
                ) as span:
                    # 2.Review whether what is being done is legal
                    approve, comments = await self.review(llm_content, self)
                    reply_message.review_info = AgentReviewInfo(
                        approve=approve,
                        comments=comments,
                    )
                    span.metadata["approve"] = approve
                    span.metadata["comments"] = comments

                act_extent_param = self.prepare_act_param(
                    received_message=received_message,
                    sender=sender,
                    rely_messages=rely_messages,
                    historical_dialogues=historical_dialogues,
                    reply_message=reply_message,
                )
                with root_tracer.start_span(
                    "agent.generate_reply.act",
                    metadata={
                        "llm_reply": llm_content,
                        "sender": sender.name,
                        "reviewer": reviewer.name if reviewer else None,
                        "act_extent_param": act_extent_param,
                    },
                ) as span:
                    # 3.Act based on the results of your thinking
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
                    span.metadata["action_report"] = (
                        act_out.to_dict() if act_out else None
                    )

                with root_tracer.start_span(
                    "agent.generate_reply.verify",
                    metadata={
                        "llm_reply": llm_content,
                        "sender": sender.name,
                        "reviewer": reviewer.name if reviewer else None,
                    },
                ) as span:
                    # 4.Reply information verification
                    check_pass, reason = await self.verify(
                        reply_message, sender, reviewer
                    )
                    is_success = check_pass
                    span.metadata["check_pass"] = check_pass
                    span.metadata["reason"] = reason

                question: str = received_message.content or ""
                ai_message: str = llm_content
                # 5.Optimize wrong answers myself
                if not check_pass:
                    if not act_out.have_retry:
                        logger.warning("No retry available!")
                        break
                    fail_reason = reason
                    await self.write_memories(
                        question=question,
                        ai_message=ai_message,
                        action_output=act_out,
                        check_pass=check_pass,
                        check_fail_reason=fail_reason,
                    )
                else:
                    # Successful reply
                    observation = act_out.observations
                    await self.write_memories(
                        question=question,
                        ai_message=ai_message,
                        action_output=act_out,
                        check_pass=check_pass,
                    )
                    if self.run_mode != AgentRunMode.LOOP or act_out.terminate:
                        logger.debug(f"Agent {self.name} reply success!{reply_message}")
                        break

                # Continue to run the next round
                self.current_retry_counter += 1
                # Send error messages and issue new problem-solving instructions
                if self.current_retry_counter < self.max_retry_count:
                    await self.send(
                        reply_message, sender, reviewer, request_reply=False
                    )

            reply_message.success = is_success
            # 6.final message adjustment
            await self.adjust_final_message(is_success, reply_message)
            return reply_message

        except Exception as e:
            logger.exception("Generate reply exception!")
            err_message = AgentMessage(content=str(e))
            err_message.rounds = 101
            err_message.success = False
            return err_message
        finally:
            if reply_message:
                root_span.metadata["reply_message"] = reply_message.to_dict()
            root_span.end()

    async def thinking(
        self,
        messages: List[AgentMessage],
        reply_message_id: str,
        sender: Optional[Agent] = None,
        prompt: Optional[str] = None,
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
                ):
                    current_thinking, current_content = output

                    if self.not_null_agent_context.incremental:
                        res_thinking = current_thinking[len(prev_thinking) :]
                        res_content = current_content[len(prev_content) :]
                        prev_thinking = current_thinking
                        prev_content = current_content

                    else:
                        res_thinking = (
                            current_thinking.strip().replace("\\n", "\n")
                            if current_thinking
                            else current_thinking
                        )
                        res_content = (
                            current_content.strip().replace("\\n", "\n")
                            if current_content
                            else current_content
                        )
                        prev_thinking = res_thinking
                        prev_content = res_content

                    if self.stream_out:
                        temp_message = {
                            "uid": reply_message_id,
                            "type": "incr",
                            "app_code": self.agent_context.gpts_app_code,
                            "sender": self.name or self.role,
                            "model": llm_model,
                            "thinking": res_thinking,
                            "content": res_content,
                            "avatar": self.avatar,
                        }
                        if not self.not_null_agent_context.output_process_message:
                            if self.is_final_role:
                                await self.memory.gpts_memory.push_message(
                                    self.not_null_agent_context.conv_id,
                                    stream_msg=temp_message,
                                    is_first_chunk=is_first_chunk,
                                    incremental=self.not_null_agent_context.incremental,
                                )
                        else:
                            await self.memory.gpts_memory.push_message(
                                self.not_null_agent_context.conv_id,
                                stream_msg=temp_message,
                                is_first_chunk=is_first_chunk,
                                incremental=self.not_null_agent_context.incremental,
                            )

                        if is_first_chunk:
                            is_first_chunk = False

                return prev_thinking, prev_content, llm_model
            except LLMChatError as e:
                logger.exception(f"model:{llm_model} generate Failed!{str(e)}")
                if e.original_exception and e.original_exception > 0:
                    ## TODO 可以尝试发一个系统提示消息

                    ## 模型调用返回错误码大于0，可以使用其他模型兜底重试，小于0 没必要重试直接返回异常     # noqa: E501
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

    async def review(self, message: Optional[str], censored: Agent) -> Tuple[bool, Any]:
        """Review the message based on the censored message."""
        return True, None

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
                real_action = action.parse_action(
                    ai_message, default_action=action, **kwargs
                )
                if real_action is None:
                    continue

                last_out = await real_action.run(
                    ai_message=message.content if message.content else "",
                    resource=None,
                    rely_action_out=last_out,
                    render_protocol=self.memory.gpts_memory.vis_converter(
                        self.not_null_agent_context.conv_id
                    ),
                    message_id=message.message_id,
                    **kwargs,
                )
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
        sender: Agent,
        reviewer: Optional[Agent] = None,
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

    async def initiate_chat(
        self,
        recipient: Agent,
        reviewer: Optional[Agent] = None,
        message: Optional[str] = None,
        request_reply: bool = True,
        is_retry_chat: bool = False,
        last_speaker_name: Optional[str] = None,
        message_rounds: int = 0,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
        **context,
    ):
        """Initiate a chat with another agent.

        Args:
            recipient (Agent): The recipient agent.
            reviewer (Agent): The reviewer agent.
            message (str): The message to send.
        """
        agent_message = AgentMessage.from_messages(
            [
                {
                    "content": message,
                    "current_goal": message,
                    "rounds": message_rounds,
                    "context": context,
                }
            ]
        )[0]
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
            await self.send(
                agent_message,
                recipient,
                reviewer,
                historical_dialogues=historical_dialogues,
                rely_messages=rely_messages,
                request_reply=request_reply,
                is_retry_chat=is_retry_chat,
                last_speaker_name=last_speaker_name,
            )

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
        sender: Agent,
        reciver: Optional[Agent] = None,
    ) -> bool:
        gpts_message: GptsMessage = message.to_gpts_message(
            sender=sender, role=role, receiver=reciver
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

    def _print_received_message(self, message: AgentMessage, sender: Agent):
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

    async def _a_process_received_message(self, message: AgentMessage, sender: Agent):
        valid = await self._a_append_message(message, None, sender, self)
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

    def convert_to_agent_message(
        self,
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
            llm_strategy_cls = get_llm_strategy_manager().get_llm_strategy_cls(
                self.not_null_llm_config.llm_strategy
            )
            if not llm_strategy_cls:
                raise ValueError(
                    f"Configured model policy not found {self.not_null_llm_config.llm_strategy}!"  # noqa: E501
                )
            llm_strategy = llm_strategy_cls(
                self.not_null_llm_config.llm_client,
                self.not_null_llm_config.strategy_context,
            )

            return await llm_strategy.next_llm(excluded_models=excluded_models)
        except Exception as e:
            logger.error(f"{self.role} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")

    async def init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
        sender: Optional[Agent] = None,
        rounds: Optional[int] = None,
    ) -> AgentMessage:
        """Create a new message from the received message.

        Initialize a new message from the received message

        Args:
            received_message(AgentMessage): The received message

        Returns:
            AgentMessage: A new message
        """
        new_message = AgentMessage.init_new(
            content="",
            current_goal=received_message.current_goal,
            goal_id=received_message.goal_id,
            context=received_message.context,
            rounds=rounds if rounds is not None else received_message.rounds + 1,
            name=self.name,
            role=self.role,
            show_message=self.show_message,
        )
        await self._a_append_message(new_message, None, self)
        return new_message

    async def _a_init_reply_message(
        self,
        received_message: AgentMessage,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> Optional[AgentMessage]:
        """Create a new message from the received message.

        If return not None, the `init_reply_message` method will not be called.
        """
        return None

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
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: bool = False,
        force_use_historical: bool = False,
    ) -> Tuple[List[AgentMessage], Optional[Dict], Optional[str], Optional[str]]:
        observation = received_message.content
        if not observation:
            raise ValueError("The received message content is empty!")
        memories = await self.read_memories(observation)
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
            most_recent_memories=memories,
            resource_vars=resource_vars,
            context=context,
            is_retry_chat=is_retry_chat,
        )
        user_prompt = await self.build_prompt(
            question=observation,
            is_system=False,
            most_recent_memories=memories,
            resource_vars=resource_vars,
            **context,
        )
        if not user_prompt:
            user_prompt = "Observation: "

        agent_messages = []
        if system_prompt:
            agent_messages.append(
                AgentMessage(
                    content=system_prompt,
                    role=ModelMessageRoleType.SYSTEM,
                )
            )
        if (historical_dialogues and not has_memories) or force_use_historical:
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

        # Current user input information
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
