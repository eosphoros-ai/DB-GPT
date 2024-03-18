from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from dbgpt.agent.actions.action import Action, ActionOutput
from dbgpt.agent.agents.agent_new import Agent, AgentContext
from dbgpt.agent.agents.llm.llm import LLMConfig, LLMStrategyType
from dbgpt.agent.agents.llm.llm_client import AIWrapper
from dbgpt.agent.agents.role import Role
from dbgpt.agent.memory.base import GptsMessage
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.agent.resource.resource_api import AgentResource, ResourceClient
from dbgpt.agent.resource.resource_loader import ResourceLoader
from dbgpt.core.interface.message import ModelMessageRoleType
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.utils import colored

logger = logging.getLogger(__name__)


class ConversableAgent(Role, Agent):
    agent_context: Optional[AgentContext] = None
    actions: List[Action] = Field(default_factory=list)
    resources: List[AgentResource] = Field(default_factory=list)
    llm_config: Optional[LLMConfig] = None
    memory: GptsMemory = Field(default_factory=GptsMemory)
    resource_loader: Optional[ResourceLoader] = None
    max_retry_count: int = 3
    consecutive_auto_reply_counter: int = 0
    llm_client: Optional[AIWrapper] = None
    oai_system_message: List[Dict] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        Role.__init__(self, **kwargs)
        Agent.__init__(self)

    def init_system_message(self):
        content = self.prompt_template()
        self.oai_system_message = [
            {"content": content, "role": ModelMessageRoleType.SYSTEM}
        ]

    def check_available(self):
        self.identity_check()
        # check run context
        if self.agent_context is None:
            raise ValueError(
                f"{self.name}[{self.profile}] Missing context in which agent is running！"
            )

        # rource check
        for resource in self.resources:
            if (
                self.resource_loader is None
                or self.resource_loader.get_resesource_api(resource.type) is None
            ):
                raise ValueError(
                    f"Resource {resource.type}:{resource.value} missing resource loader implementation,unable to read resources!"
                )

        # action check
        if self.actions and len(self.actions) > 0:
            have_resource_types = [item.type for item in self.resources]
            for action in self.actions:
                if (
                    action.resource_need
                    and action.resource_need not in have_resource_types
                ):
                    raise ValueError(
                        f"{self.name}[{self.profile}] Missing resources required for runtime！"
                    )
        else:
            if not self.is_human and not self.is_team:
                raise ValueError(
                    f"This agent {self.name}[{self.profile}] is missing action modules."
                )
        # llm check
        if not self.is_human:
            if self.llm_config is None or self.llm_config.llm_client is None:
                raise ValueError(
                    f"{self.name}[{self.profile}] Model configuration is missing or model service is unavailable！"
                )

    async def a_preload_resource(self):
        pass

    async def build(self) -> ConversableAgent:
        # Check if agent is available
        self.check_available()

        self.language = self.agent_context.language
        # Preload resources
        await self.a_preload_resource()
        # Initialize resource loader
        for action in self.actions:
            action.init_resource_loader(self.resource_loader)

        # Initialize system messages
        self.init_system_message()

        # Initialize LLM Server
        if not self.is_human:
            self.llm_client = AIWrapper(llm_client=self.llm_config.llm_client)
        return self

    def bind(self, target: Any) -> ConversableAgent:
        if isinstance(target, LLMConfig):
            self.llm_config = target
        elif isinstance(target, GptsMemory):
            self.memory = target
        elif isinstance(target, AgentContext):
            self.agent_context = target
        elif isinstance(target, ResourceLoader):
            self.resource_loader = target
        elif isinstance(target, list):
            if target and len(target) > 0:
                if self._is_list_of_type(target, Action):
                    self.actions.extend(target)
                elif self._is_list_of_type(target, AgentResource):
                    self.resources = target
        return self

    async def a_send(
        self,
        message: Union[Dict, str],
        recipient: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = True,
        is_recovery: Optional[bool] = False,
    ) -> None:
        await recipient.a_receive(
            message=message,
            sender=self,
            reviewer=reviewer,
            request_reply=request_reply,
            is_recovery=is_recovery,
        )

    async def a_receive(
        self,
        message: Optional[Dict],
        sender: Agent,
        reviewer: Optional[Agent] = None,
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
    ) -> None:
        await self._a_process_received_message(message, sender)
        if request_reply is False or request_reply is None:
            return

        if not self.is_human:
            is_success, reply = await self.a_generate_reply(
                recive_message=message, sender=sender, reviewer=reviewer
            )
            if reply is not None:
                await self.a_send(reply, sender)

    def prepare_act_param(self) -> Optional[Dict]:
        return {}

    async def a_generate_reply(
        self,
        recive_message: Optional[Dict],
        sender: Agent,
        reviewer: Agent = None,
        rely_messages: Optional[List[Dict]] = None,
    ):
        logger.info(
            f"generate agent reply!sender={sender}, rely_messages_len={rely_messages}"
        )
        try:
            reply_message = self._init_reply_message(recive_message=recive_message)
            await self._system_message_assembly(
                recive_message["content"], reply_message.get("context", None)
            )

            fail_reason = None
            current_retry_counter = 0
            is_sucess = True
            while current_retry_counter < self.max_retry_count:
                if current_retry_counter > 0:
                    retry_message = self._init_reply_message(
                        recive_message=recive_message
                    )
                    retry_message["content"] = fail_reason
                    retry_message["current_goal"] = recive_message.get(
                        "current_goal", None
                    )
                    # The current message is a self-optimized message that needs to be recorded.
                    # It is temporarily set to be initiated by the originating end to facilitate the organization of historical memory context.
                    await sender.a_send(
                        retry_message, self, reviewer, request_reply=False
                    )

                # 1.Think about how to do things
                llm_reply, model_name = await self.a_thinking(
                    self._load_thinking_messages(recive_message, sender, rely_messages)
                )
                reply_message["model_name"] = model_name
                reply_message["content"] = llm_reply

                # 2.Review whether what is being done is legal
                approve, comments = await self.a_review(llm_reply, self)
                reply_message["review_info"] = {
                    "approve": approve,
                    "comments": comments,
                }

                # 3.Act based on the results of your thinking
                act_extent_param = self.prepare_act_param()
                act_out: ActionOutput = await self.a_act(
                    message=llm_reply,
                    sender=sender,
                    reviewer=reviewer,
                    **act_extent_param,
                )
                reply_message["action_report"] = act_out.dict()

                # 4.Reply information verification
                check_paas, reason = await self.a_verify(
                    reply_message, sender, reviewer
                )
                is_sucess = check_paas
                # 5.Optimize wrong answers myself
                if not check_paas:
                    current_retry_counter += 1
                    # Send error messages and issue new problem-solving instructions
                    if current_retry_counter < self.max_retry_count:
                        await self.a_send(
                            reply_message, sender, reviewer, request_reply=False
                        )
                    fail_reason = reason
                else:
                    break
            return is_sucess, reply_message

        except Exception as e:
            logger.exception("Generate reply exception!")
            return False, {"content": str(e)}

    async def a_thinking(
        self, messages: Optional[List[Dict]], prompt: Optional[str] = None
    ) -> Union[str, Dict, None]:
        last_model = None
        last_err = None
        retry_count = 0
        # LLM inference automatically retries 3 times to reduce interruption probability caused by speed limit and network stability
        while retry_count < 3:
            llm_model = await self._a_select_llm_model(last_model)
            try:
                if prompt:
                    messages = self._new_system_message(prompt) + messages
                else:
                    messages = self.oai_system_message + messages

                response = await self.llm_client.create(
                    context=messages[-1].pop("context", None),
                    messages=messages,
                    llm_model=llm_model,
                    max_new_tokens=self.agent_context.max_new_tokens,
                    temperature=self.agent_context.temperature,
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

    async def a_review(
        self, message: Union[Dict, str], censored: Agent
    ) -> Tuple[bool, Any]:
        return True, None

    async def a_act(
        self,
        message: Optional[str],
        sender: Optional[ConversableAgent] = None,
        reviewer: Optional[ConversableAgent] = None,
        **kwargs,
    ) -> Optional[ActionOutput]:
        last_out = None
        for action in self.actions:
            # Select the resources required by acton
            need_resource = None
            if self.resources and len(self.resources) > 0:
                for item in self.resources:
                    if item.type == action.resource_need:
                        need_resource = item
                        break

            last_out: ActionOutput = await action.a_run(
                ai_message=message,
                resource=need_resource,
                rely_action_out=last_out,
                **kwargs,
            )
        return last_out

    async def a_correctness_check(self, message: Optional[Dict]):
        ##  Verify the correctness of the results
        return True, None

    async def a_verify(
        self, message: Optional[Dict], sender: Agent, reviewer: Agent, **kwargs
    ) -> Union[str, Dict, None]:
        ## Check approval results
        if "review_info" in message:
            review_info = message.get("review_info")
            if review_info and not review_info.get("approve"):
                return False, review_info.get("comments")

        ## Check action run results
        action_output: ActionOutput = ActionOutput.from_dict(
            message.get("action_report", None)
        )
        if action_output:
            if not action_output.is_exe_success:
                return False, action_output.content
            elif not action_output.content or len(action_output.content.strip()) < 1:
                return (
                    False,
                    f"The current execution result is empty. Please rethink the question and background and generate a new answer.. ",
                )

        ## agent output correctness check
        return await self.a_correctness_check(message)

    async def a_initiate_chat(
        self,
        recipient: "ConversableAgent",
        reviewer: "Agent" = None,
        clear_history: Optional[bool] = True,
        **context,
    ):
        await self.a_send(
            {
                "content": context["message"],
                "current_goal": context["message"],
            },
            recipient,
            reviewer,
            request_reply=True,
        )

    #######################################################################
    ## Private Function Begin
    #######################################################################

    def _init_actions(self, actions: List[Action] = None):
        self.actions = []
        for idx, action in enumerate(actions):
            if not isinstance(action, Action):
                self.actions.append(action())

    async def _a_append_message(
        self, message: Optional[Dict], role, sender: Agent
    ) -> bool:
        self.consecutive_auto_reply_counter = sender.consecutive_auto_reply_counter + 1
        oai_message = {
            k: message[k]
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
            if k in message
        }

        gpts_message: GptsMessage = GptsMessage(
            conv_id=self.agent_context.conv_id,
            sender=sender.profile,
            receiver=self.profile,
            role=role,
            rounds=self.consecutive_auto_reply_counter,
            current_goal=oai_message.get("current_goal", None),
            content=oai_message.get("content", None),
            context=json.dumps(oai_message["context"], ensure_ascii=False)
            if "context" in oai_message
            else None,
            review_info=json.dumps(oai_message["review_info"], ensure_ascii=False)
            if "review_info" in oai_message
            else None,
            action_report=json.dumps(oai_message["action_report"], ensure_ascii=False)
            if "action_report" in oai_message
            else None,
            model_name=oai_message.get("model_name", None),
        )

        self.memory.message_memory.append(gpts_message)
        return True

    def _print_received_message(self, message: Union[Dict], sender: ConversableAgent):
        # print the message received
        print("\n", "-" * 80, flush=True, sep="")
        print(
            colored(sender.name if sender.name else sender.profile, "yellow"),
            "(to",
            f"{self.name if self.name else self.profile})-[{message.get('model_name', '')}]:\n",
            flush=True,
        )

        content = json.dumps(message.get("content"), ensure_ascii=False)
        if content is not None:
            print(content, flush=True)

        review_info = message.get("review_info", None)
        if review_info:
            approve_print = f">>>>>>>>{sender.name if sender.name else sender.profile} Review info: \n {'Pass' if review_info.get('approve') else 'Reject'}.{review_info.get('comments')}"
            print(colored(approve_print, "green"), flush=True)

        action_report = message.get("action_report", None)
        if action_report:
            action_print = f">>>>>>>>{sender.name if sender.name else sender.profile} Action report: \n{'execution succeeded' if action_report['is_exe_success'] else 'execution failed'},\n{action_report['content']}"
            print(colored(action_print, "blue"), flush=True)

        print("\n", "-" * 80, flush=True, sep="")

    async def _a_process_received_message(self, message: Optional[Dict], sender: Agent):
        valid = await self._a_append_message(message, None, sender)
        if not valid:
            raise ValueError(
                "Received message can't be converted into a valid ChatCompletion message. Either content or function_call must be provided."
            )

        self._print_received_message(message, sender)

    async def _system_message_assembly(
        self, qustion: Optional[str], context: Optional[Dict] = None
    ):
        ## system message
        self.init_system_message()
        if len(self.oai_system_message) > 0:
            resource_prompt_list = []
            for item in self.resources:
                resource_client = self.resource_loader.get_resesource_api(item.type)
                resource_prompt_list.append(
                    await resource_client.get_resource_prompt(
                        self.agent_context.conv_id, item, qustion
                    )
                )
            if context is None:
                context = {}

            resource_prompt = ""
            if len(resource_prompt_list) > 0:
                resource_prompt = "RESOURCES:" + "\n".join(resource_prompt_list)

            out_schema = ""
            if self.actions and len(self.actions) > 0:
                out_schema = self.actions[0].ai_out_schema
            for message in self.oai_system_message:
                new_content = message["content"].format(
                    resource_prompt=resource_prompt,
                    out_schema=out_schema,
                    **context,
                )
                message["content"] = new_content

    def _excluded_models(
        self,
        all_models: Optional[List[str]],
        order_llms: Optional[List[str]] = [],
        excluded_models: Optional[List[str]] = [],
    ):
        can_uses = []
        if order_llms and len(order_llms) > 0:
            for llm_name in order_llms:
                if llm_name in all_models:
                    if not excluded_models or llm_name not in excluded_models:
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
            all_models = await self.llm_config.llm_client.models()
            all_model_names = [item.model for item in all_models]
            # TODO Currently only two strategies, priority and default, are implemented.
            if self.llm_config.llm_strategy == LLMStrategyType.Priority:
                priority: List[str] = []
                if self.llm_config.strategy_context is not None:
                    priority: List[str] = json.loads(self.llm_config.strategy_context)
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
            logger.error(f"{self.profile} get next llm failed!{str(e)}")
            raise ValueError(f"Failed to allocate model service,{str(e)}!")

    def _init_reply_message(self, recive_message):
        """
        Initialize a new message from the received message
        Args:
            recive_message:

        Returns:

        """
        new_message = {}
        new_message["context"] = recive_message.get("context", None)
        new_message["current_goal"] = recive_message.get("current_goal", None)
        return new_message

    def _convert_to_ai_message(
        self, gpts_messages: Optional[List[GptsMessage]]
    ) -> List[Dict]:
        oai_messages: List[Dict] = []
        # Based on the current agent, all messages received are user, and all messages sent are assistant.
        for item in gpts_messages:
            role = ""
            if item.role:
                role = role
            else:
                if item.receiver == self.profile:
                    role = ModelMessageRoleType.HUMAN
                elif item.sender == self.profile:
                    role = ModelMessageRoleType.AI
                else:
                    continue

            # Message conversion, priority is given to converting execution results, and only model output results will be used if not.
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
                {
                    "content": content,
                    "role": role,
                    "context": json.loads(item.context)
                    if item.context is not None
                    else None,
                }
            )
        return oai_messages

    def _load_thinking_messages(
        self,
        receive_message: Optional[Dict],
        sender,
        rely_messages: Optional[List[Dict]] = None,
    ) -> Optional[List[Dict]]:
        current_goal = receive_message.get("current_goal", None)

        ### Convert and tailor the information in collective memory into contextual memory available to the current Agent
        current_goal_messages = self._convert_to_ai_message(
            self.memory.message_memory.get_between_agents(
                self.agent_context.conv_id, self.profile, sender.profile, current_goal
            )
        )

        # When there is no target and context, the current received message is used as the target problem
        if current_goal_messages is None or len(current_goal_messages) <= 0:
            receive_message["role"] = ModelMessageRoleType.HUMAN
            current_goal_messages = [receive_message]

        ### relay messages
        cut_messages = []
        if rely_messages:
            ## When directly relying on historical messages, use the execution result content as a dependency
            for rely_message in rely_messages:
                action_report: Optional[ActionOutput] = ActionOutput.from_dict(
                    rely_message.get("action_report", None)
                )
                if action_report:
                    rely_message["content"] = action_report.content

            cut_messages.extend(rely_messages)

        # TODO: allocate historical information based on token budget
        if len(current_goal_messages) < 5:
            cut_messages.extend(current_goal_messages)
        else:
            # For the time being, the smallest size of historical message records will be used by default.
            # Use the first two rounds of messages to understand the initial goals
            cut_messages.extend(current_goal_messages[:2])
            # Use information from the last three rounds of communication to ensure that current thinking knows what happened and what to do in the last communication
            cut_messages.extend(current_goal_messages[-3:])
        return cut_messages

    def _new_system_message(self, content):
        """Return the system message."""
        return [{"content": content, "role": ModelMessageRoleType.SYSTEM}]

    def _is_list_of_type(self, lst: List[Any], type_cls: type) -> bool:
        return all(isinstance(item, type_cls) for item in lst)
