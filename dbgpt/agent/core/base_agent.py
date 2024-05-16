"""Base agent class for conversable agents."""

import asyncio
import json
import logging
from concurrent.futures import Executor, ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, cast

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import LLMClient, ModelMessageRoleType
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.executor_utils import blocking_func_to_async
from dbgpt.util.tracer import SpanType, root_tracer
from dbgpt.util.utils import colored

from ..resource.base import Resource
from ..util.llm.llm import LLMConfig, LLMStrategyType
from ..util.llm.llm_client import AIWrapper
from .action.base import Action, ActionOutput
from .agent import Agent, AgentContext, AgentMessage, AgentReviewInfo
from .memory.agent_memory import AgentMemory
from .memory.gpts.base import GptsMessage
from .memory.gpts.gpts_memory import GptsMemory
from .role import Role

logger = logging.getLogger(__name__)


class ConversableAgent(Role, Agent):
    """ConversableAgent is an agent that can communicate with other agents."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agent_context: Optional[AgentContext] = Field(None, description="Agent context")
    actions: List[Action] = Field(default_factory=list)
    resource: Optional[Resource] = Field(None, description="Resource")
    llm_config: Optional[LLMConfig] = None
    max_retry_count: int = 3
    consecutive_auto_reply_counter: int = 0
    llm_client: Optional[AIWrapper] = None
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
                f"{self.name}[{self.role}] Missing context in which agent is "
                f"running!"
            )

        # action check
        if self.actions and len(self.actions) > 0:
            for action in self.actions:
                if action.resource_need and (
                    not self.resource
                    or not self.resource.get_resource_by_type(action.resource_need)
                ):
                    raise ValueError(
                        f"{self.name}[{self.role}] Missing resources required for "
                        "runtime！"
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
        if not self.is_human:
            if not self.llm_config or not self.llm_config.llm_client:
                raise ValueError("LLM client is not initialized！")
            self.llm_client = AIWrapper(llm_client=self.llm_config.llm_client)
            self.memory.initialize(
                self.name,
                self.llm_config.llm_client,
                importance_scorer=self.memory_importance_scorer,
                insight_extractor=self.memory_insight_extractor,
            )
            # Clone the memory structure
            self.memory = self.memory.structure_clone()
        return self

    def bind(self, target: Any) -> "ConversableAgent":
        """Bind the resources to the agent."""
        if isinstance(target, LLMConfig):
            self.llm_config = target
        elif isinstance(target, GptsMemory):
            raise ValueError("GptsMemory is not supported!")
        elif isinstance(target, AgentContext):
            self.agent_context = target
        elif isinstance(target, Resource):
            self.resource = target
        elif isinstance(target, AgentMemory):
            self.memory = target
        return self

    async def send(
        self,
        message: AgentMessage,
        recipient: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
    ) -> None:
        """Send a message to recipient agent."""
        with root_tracer.start_span(
            "agent.send",
            metadata={
                "sender": self.name,
                "recipient": recipient.name,
                "reviewer": reviewer.name if reviewer else None,
                "agent_message": message.to_dict(),
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
            )

    async def receive(
        self,
        message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
    ) -> None:
        """Receive a message from another agent."""
        with root_tracer.start_span(
            "agent.receive",
            metadata={
                "sender": sender.name,
                "recipient": self.name,
                "reviewer": reviewer.name if reviewer else None,
                "agent_message": message.to_dict(),
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
                reply = await self.generate_reply(
                    received_message=message, sender=sender, reviewer=reviewer
                )
                if reply is not None:
                    await self.send(reply, sender)

    def prepare_act_param(self) -> Dict[str, Any]:
        """Prepare the parameters for the act method."""
        return {}

    async def generate_reply(
        self,
        received_message: AgentMessage,
        sender: Agent,
        reviewer: Optional[Agent] = None,
        rely_messages: Optional[List[AgentMessage]] = None,
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
                "received_message": received_message.to_dict(),
                "conv_uid": self.not_null_agent_context.conv_id,
                "rely_messages": (
                    [msg.to_dict() for msg in rely_messages] if rely_messages else None
                ),
            },
        )

        try:
            with root_tracer.start_span(
                "agent.generate_reply._init_reply_message",
                metadata={
                    "received_message": received_message.to_dict(),
                },
            ) as span:
                # initialize reply message
                reply_message: AgentMessage = self._init_reply_message(
                    received_message=received_message
                )
                span.metadata["reply_message"] = reply_message.to_dict()

            fail_reason = None
            current_retry_counter = 0
            is_success = True
            while current_retry_counter < self.max_retry_count:
                if current_retry_counter > 0:
                    retry_message = self._init_reply_message(
                        received_message=received_message
                    )
                    retry_message.content = fail_reason
                    retry_message.current_goal = received_message.current_goal
                    # The current message is a self-optimized message that needs to be
                    # recorded.
                    # It is temporarily set to be initiated by the originating end to
                    # facilitate the organization of historical memory context.
                    await sender.send(
                        retry_message, self, reviewer, request_reply=False
                    )

                thinking_messages = await self._load_thinking_messages(
                    received_message,
                    sender,
                    rely_messages,
                    context=reply_message.get_dict_context(),
                )
                with root_tracer.start_span(
                    "agent.generate_reply.thinking",
                    metadata={
                        "thinking_messages": [
                            msg.to_dict() for msg in thinking_messages
                        ],
                    },
                ) as span:
                    # 1.Think about how to do things
                    llm_reply, model_name = await self.thinking(thinking_messages)
                    reply_message.model_name = model_name
                    reply_message.content = llm_reply
                    span.metadata["llm_reply"] = llm_reply
                    span.metadata["model_name"] = model_name

                with root_tracer.start_span(
                    "agent.generate_reply.review",
                    metadata={"llm_reply": llm_reply, "censored": self.name},
                ) as span:
                    # 2.Review whether what is being done is legal
                    approve, comments = await self.review(llm_reply, self)
                    reply_message.review_info = AgentReviewInfo(
                        approve=approve,
                        comments=comments,
                    )
                    span.metadata["approve"] = approve
                    span.metadata["comments"] = comments

                act_extent_param = self.prepare_act_param()
                with root_tracer.start_span(
                    "agent.generate_reply.act",
                    metadata={
                        "llm_reply": llm_reply,
                        "sender": sender.name,
                        "reviewer": reviewer.name if reviewer else None,
                        "act_extent_param": act_extent_param,
                    },
                ) as span:
                    # 3.Act based on the results of your thinking
                    act_out: Optional[ActionOutput] = await self.act(
                        message=llm_reply,
                        sender=sender,
                        reviewer=reviewer,
                        **act_extent_param,
                    )
                    if act_out:
                        reply_message.action_report = act_out.to_dict()
                    span.metadata["action_report"] = (
                        act_out.to_dict() if act_out else None
                    )

                with root_tracer.start_span(
                    "agent.generate_reply.verify",
                    metadata={
                        "llm_reply": llm_reply,
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
                ai_message: str = llm_reply or ""
                # 5.Optimize wrong answers myself
                if not check_pass:
                    current_retry_counter += 1
                    # Send error messages and issue new problem-solving instructions
                    if current_retry_counter < self.max_retry_count:
                        await self.send(
                            reply_message, sender, reviewer, request_reply=False
                        )
                    fail_reason = reason
                    await self.save_to_memory(
                        question=question,
                        ai_message=ai_message,
                        action_output=act_out,
                        check_pass=check_pass,
                        check_fail_reason=fail_reason,
                    )
                else:
                    await self.save_to_memory(
                        question=question,
                        ai_message=ai_message,
                        action_output=act_out,
                        check_pass=check_pass,
                    )
                    break
            reply_message.success = is_success
            return reply_message

        except Exception as e:
            logger.exception("Generate reply exception!")
            err_message = AgentMessage(content=str(e))
            err_message.success = False
            return err_message
        finally:
            root_span.metadata["reply_message"] = reply_message.to_dict()
            root_span.end()

    async def thinking(
        self, messages: List[AgentMessage], prompt: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
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
                if prompt:
                    llm_messages = _new_system_message(prompt) + llm_messages

                if not self.llm_client:
                    raise ValueError("LLM client is not initialized!")
                response = await self.llm_client.create(
                    context=llm_messages[-1].pop("context", None),
                    messages=llm_messages,
                    llm_model=llm_model,
                    max_new_tokens=self.not_null_agent_context.max_new_tokens,
                    temperature=self.not_null_agent_context.temperature,
                )
                return response, llm_model
            except LLMChatError as e:
                logger.error(f"model:{llm_model} generate Failed!{str(e)}")
                retry_count += 1
                last_model = llm_model
                last_err = str(e)
                await asyncio.sleep(10)

        if last_err:
            raise ValueError(last_err)
        else:
            raise ValueError("LLM model inference failed!")

    async def review(self, message: Optional[str], censored: Agent) -> Tuple[bool, Any]:
        """Review the message based on the censored message."""
        return True, None

    async def act(
        self,
        message: Optional[str],
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        **kwargs,
    ) -> Optional[ActionOutput]:
        """Perform actions."""
        last_out: Optional[ActionOutput] = None
        for i, action in enumerate(self.actions):
            # Select the resources required by acton
            if action.resource_need and self.resource:
                need_resources = self.resource.get_resource_by_type(
                    action.resource_need
                )
            else:
                need_resources = []

            if not message:
                raise ValueError("The message content is empty!")

            with root_tracer.start_span(
                "agent.act.run",
                metadata={
                    "message": message,
                    "sender": sender.name if sender else None,
                    "recipient": self.name,
                    "reviewer": reviewer.name if reviewer else None,
                    "need_resource": need_resources[0].name if need_resources else None,
                    "rely_action_out": last_out.to_dict() if last_out else None,
                    "conv_uid": self.not_null_agent_context.conv_id,
                    "action_index": i,
                    "total_action": len(self.actions),
                },
            ) as span:
                last_out = await action.run(
                    ai_message=message,
                    resource=None,
                    rely_action_out=last_out,
                    **kwargs,
                )
                span.metadata["action_out"] = last_out.to_dict() if last_out else None
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
        action_output: Optional[ActionOutput] = ActionOutput.from_dict(
            message.action_report
        )
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
    ):
        """Initiate a chat with another agent.

        Args:
            recipient (Agent): The recipient agent.
            reviewer (Agent): The reviewer agent.
            message (str): The message to send.
        """
        agent_message = AgentMessage(content=message, current_goal=message)
        with root_tracer.start_span(
            "agent.initiate_chat",
            span_type=SpanType.AGENT,
            metadata={
                "sender": self.name,
                "recipient": recipient.name,
                "reviewer": reviewer.name if reviewer else None,
                "agent_message": agent_message.to_dict(),
                "conv_uid": self.not_null_agent_context.conv_id,
            },
        ):
            await self.send(
                agent_message,
                recipient,
                reviewer,
                request_reply=True,
            )

    #######################################################################
    # Private Function Begin
    #######################################################################

    def _init_actions(self, actions: List[Type[Action]]):
        self.actions = []
        for idx, action in enumerate(actions):
            if issubclass(action, Action):
                self.actions.append(action())

    async def _a_append_message(
        self, message: AgentMessage, role, sender: Agent
    ) -> bool:
        new_sender = cast(ConversableAgent, sender)
        self.consecutive_auto_reply_counter = (
            new_sender.consecutive_auto_reply_counter + 1
        )
        message_dict = message.to_dict()
        oai_message = {
            k: message_dict[k]
            for k in (
                "content",
                "function_call",
                "name",
                "context",
                "action_report",
                "review_info",
                "current_goal",
                "model_name",
            )
            if k in message_dict
        }

        gpts_message: GptsMessage = GptsMessage(
            conv_id=self.not_null_agent_context.conv_id,
            sender=sender.role,
            receiver=self.role,
            role=role,
            rounds=self.consecutive_auto_reply_counter,
            current_goal=oai_message.get("current_goal", None),
            content=oai_message.get("content", None),
            context=(
                json.dumps(oai_message["context"], ensure_ascii=False)
                if "context" in oai_message
                else None
            ),
            review_info=(
                json.dumps(oai_message["review_info"], ensure_ascii=False)
                if "review_info" in oai_message
                else None
            ),
            action_report=(
                json.dumps(oai_message["action_report"], ensure_ascii=False)
                if "action_report" in oai_message
                else None
            ),
            model_name=oai_message.get("model_name", None),
        )

        with root_tracer.start_span(
            "agent.save_message_to_memory",
            metadata={
                "gpts_message": gpts_message.to_dict(),
                "conv_uid": self.not_null_agent_context.conv_id,
            },
        ):
            self.memory.message_memory.append(gpts_message)
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
                if action_report["is_exe_success"]
                else "execution failed"
            )
            action_report_msg = f"{action_msg},\n{action_report['content']}"
            action_print = f">>>>>>>>{name} Action report: \n{action_report_msg}"
            print(colored(action_print, "blue"), flush=True)

        print("\n", "-" * 80, flush=True, sep="")

    async def _a_process_received_message(self, message: AgentMessage, sender: Agent):
        valid = await self._a_append_message(message, None, sender)
        if not valid:
            raise ValueError(
                "Received message can't be converted into a valid ChatCompletion"
                " message. Either content or function_call must be provided."
            )

        self._print_received_message(message, sender)

    async def generate_resource_variables(
        self, question: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate the resource variables."""
        resource_prompt = None
        if self.resource:
            resource_prompt = await self.resource.get_prompt(
                lang=self.language, question=question
            )

        out_schema: Optional[str] = ""
        if self.actions and len(self.actions) > 0:
            out_schema = self.actions[0].ai_out_schema
        return {"resource_prompt": resource_prompt, "out_schema": out_schema}

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

    def _init_reply_message(self, received_message: AgentMessage) -> AgentMessage:
        """Create a new message from the received message.

        Initialize a new message from the received message

        Args:
            received_message(AgentMessage): The received message

        Returns:
            AgentMessage: A new message
        """
        return AgentMessage(
            content=received_message.content,
            current_goal=received_message.current_goal,
        )

    def _convert_to_ai_message(
        self, gpts_messages: List[GptsMessage]
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

    async def _load_thinking_messages(
        self,
        received_message: AgentMessage,
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[AgentMessage]:
        observation = received_message.content
        if not observation:
            raise ValueError("The received message content is empty!")
        memories = await self.read_memories(observation)
        reply_message_str = ""
        if context is None:
            context = {}
        if rely_messages:
            copied_rely_messages = [m.copy() for m in rely_messages]
            # When directly relying on historical messages, use the execution result
            # content as a dependency
            for message in copied_rely_messages:
                action_report: Optional[ActionOutput] = ActionOutput.from_dict(
                    message.action_report
                )
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

        system_prompt = await self.build_prompt(
            question=observation,
            is_system=True,
            most_recent_memories=memories,
            **context,
        )
        user_prompt = await self.build_prompt(
            question=observation,
            is_system=False,
            most_recent_memories=memories,
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
        if user_prompt:
            agent_messages.append(
                AgentMessage(
                    content=user_prompt,
                    role=ModelMessageRoleType.HUMAN,
                )
            )

        return agent_messages

    def _old_load_thinking_messages(
        self,
        received_message: AgentMessage,
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
    ) -> List[AgentMessage]:
        current_goal = received_message.current_goal

        # Convert and tailor the information in collective memory into contextual
        # memory available to the current Agent

        with root_tracer.start_span(
            "agent._load_thinking_messages",
            metadata={
                "sender": sender.name,
                "recipient": self.name,
                "conv_uid": self.not_null_agent_context.conv_id,
                "current_goal": current_goal,
            },
        ) as span:
            # Get historical information from the memory
            memory_messages = self.memory.message_memory.get_between_agents(
                self.not_null_agent_context.conv_id,
                self.role,
                sender.role,
                current_goal,
            )
            span.metadata["memory_messages"] = [
                message.to_dict() for message in memory_messages
            ]
        current_goal_messages = self._convert_to_ai_message(memory_messages)

        # When there is no target and context, the current received message is used as
        # the target problem
        if current_goal_messages is None or len(current_goal_messages) <= 0:
            received_message.role = ModelMessageRoleType.HUMAN
            current_goal_messages = [received_message]

        # relay messages
        cut_messages = []
        if rely_messages:
            # When directly relying on historical messages, use the execution result
            # content as a dependency
            for rely_message in rely_messages:
                action_report: Optional[ActionOutput] = ActionOutput.from_dict(
                    rely_message.action_report
                )
                if action_report:
                    # TODO: Modify in-place, need to be optimized
                    rely_message.content = action_report.content

            cut_messages.extend(rely_messages)

        # TODO: allocate historical information based on token budget
        if len(current_goal_messages) < 5:
            cut_messages.extend(current_goal_messages)
        else:
            # For the time being, the smallest size of historical message records will
            # be used by default.
            # Use the first two rounds of messages to understand the initial goals
            cut_messages.extend(current_goal_messages[:2])
            # Use information from the last three rounds of communication to ensure
            # that current thinking knows what happened and what to do in the last
            # communication
            cut_messages.extend(current_goal_messages[-3:])
        return cut_messages


def _new_system_message(content):
    """Return the system message."""
    return [{"content": content, "role": ModelMessageRoleType.SYSTEM}]


def _is_list_of_type(lst: List[Any], type_cls: type) -> bool:
    return all(isinstance(item, type_cls) for item in lst)
