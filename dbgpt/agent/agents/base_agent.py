import asyncio
import copy
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Type, Union

from dbgpt.agent.agents.llm.llm_client import AIWrapper
from dbgpt.core.interface.message import ModelMessageRoleType
from dbgpt.util.error_types import LLMChatError
from dbgpt.util.utils import colored

from ..memory.base import GptsMessage
from ..memory.gpts_memory import GptsMemory
from .agent import Agent, AgentContext

logger = logging.getLogger(__name__)


class ConversableAgent(Agent):
    DEFAULT_SYSTEM_MESSAGE = "You are a helpful AI Assistant."
    MAX_CONSECUTIVE_AUTO_REPLY = (
        100  # maximum number of consecutive auto replies (subject to future change)
    )

    def __init__(
        self,
        name: str,
        describe: str = DEFAULT_SYSTEM_MESSAGE,
        memory: GptsMemory = GptsMemory(),
        agent_context: AgentContext = None,
        system_message: Optional[str] = DEFAULT_SYSTEM_MESSAGE,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "TERMINATE",
        default_auto_reply: Optional[Union[str, Dict, None]] = "",
    ):
        super().__init__(name, memory, describe)

        # a dictionary of conversations, default value is list
        # self._oai_messages = defaultdict(list)
        self._oai_system_message = [
            {"content": system_message, "role": ModelMessageRoleType.SYSTEM}
        ]
        self._rely_messages = []

        self.client = AIWrapper(llm_client=agent_context.llm_provider)

        self.human_input_mode = human_input_mode
        self._max_consecutive_auto_reply = (
            max_consecutive_auto_reply
            if max_consecutive_auto_reply is not None
            else self.MAX_CONSECUTIVE_AUTO_REPLY
        )
        self.consecutive_auto_reply_counter: int = 0
        self.current_retry_counter: int = 0
        self.max_retry_count: int = 5

        ## By default, the memory of 4 rounds of dialogue is retained.
        self.dialogue_memory_rounds = 5
        self._default_auto_reply = default_auto_reply
        self._reply_func_list = []
        self._max_consecutive_auto_reply_dict = {}

        self.agent_context = agent_context

    def register_reply(
        self,
        trigger: Union[Type[Agent], str, Agent, Callable[[Agent], bool], List],
        reply_func: Callable,
        position: int = 0,
        config: Optional[Any] = None,
        reset_config: Optional[Callable] = None,
    ):
        if not isinstance(trigger, (type, str, Agent, Callable, list)):
            raise ValueError(
                "trigger must be a class, a string, an agent, a callable or a list."
            )
        self._reply_func_list.insert(
            position,
            {
                "trigger": trigger,
                "reply_func": reply_func,
                "config": copy.copy(config),
                "init_config": config,
                "reset_config": reset_config,
            },
        )

    def is_termination_msg(self, message: Union[Dict, str, bool]):
        if isinstance(message, dict):
            if "is_termination" in message:
                return message.get("is_termination", False)
            else:
                return message["content"].find("TERMINATE") >= 0
        elif isinstance(message, bool):
            return message
        elif isinstance(message, str):
            return message.find("TERMINATE") >= 0
        else:
            return False

    @property
    def system_message(self):
        """Return the system message."""
        return self._oai_system_message[0]["content"]

    def update_system_message(self, system_message: str):
        """Update the system message.

        Args:
            system_message (str): system message for the ChatCompletion inference.
        """
        self._oai_system_message[0]["content"] = system_message

    def update_max_consecutive_auto_reply(
        self, value: int, sender: Optional[Agent] = None
    ):
        """Update the maximum number of consecutive auto replies.

        Args:
            value (int): the maximum number of consecutive auto replies.
            sender (Agent): when the sender is provided, only update the max_consecutive_auto_reply for that sender.
        """
        if sender is None:
            self._max_consecutive_auto_reply = value
            for k in self._max_consecutive_auto_reply_dict:
                self._max_consecutive_auto_reply_dict[k] = value
        else:
            self._max_consecutive_auto_reply_dict[sender] = value

    def max_consecutive_auto_reply(self, sender: Optional[Agent] = None) -> int:
        """The maximum number of consecutive auto replies."""
        return (
            self._max_consecutive_auto_reply
            if sender is None
            else self._max_consecutive_auto_reply_dict[sender]
        )

    @property
    # def chat_messages(self) -> Dict[Agent, List[Dict]]:
    def chat_messages(self) -> Any:
        """A dictionary of conversations from agent to list of messages."""
        all_gpts_messages = self.memory.message_memory.get_by_agent(
            self.agent_context.conv_id, self.name
        )
        return self._gpts_message_to_ai_message(all_gpts_messages)

    def last_message(self, agent: Optional[Agent] = None) -> Optional[Dict]:
        """The last message exchanged with the agent.

        Args:
            agent (Agent): The agent in the conversation.
                If None and more than one agent's conversations are found, an error will be raised.
                If None and only one conversation is found, the last message of the only conversation will be returned.

        Returns:
            The last message exchanged with the agent.
        """

        if agent is None:
            all_oai_messages = self.chat_messages()
            n_conversations = len(all_oai_messages)
            if n_conversations == 0:
                return None
            if n_conversations == 1:
                for conversation in all_oai_messages.values():
                    return conversation[-1]
            raise ValueError(
                "More than one conversation is found. Please specify the sender to get the last message."
            )

        agent_messages = self.memory.message_memory.get_between_agents(
            self.agent_context.conv_id, self.name, agent.name
        )
        if len(agent_messages) <= 0:
            raise KeyError(
                f"The agent '{agent.name}' is not present in any conversation. No history available for this agent."
            )
        return self._gpts_message_to_ai_message(agent_messages)[-1]

    @staticmethod
    def _message_to_dict(message: Union[Dict, str]):
        """Convert a message to a dictionary.

        The message can be a string or a dictionary. The string will be put in the "content" field of the new dictionary.
        """
        if isinstance(message, str):
            return {"content": message}
        elif isinstance(message, dict):
            return message
        else:
            return dict(message)

    def append_rely_message(self, message: Union[Dict, str], role) -> None:
        message = self._message_to_dict(message)
        message["role"] = role
        # create oai message to be appended to the oai conversation that can be passed to oai directly.
        self._rely_messages.append(message)

    def reset_rely_message(self) -> None:
        # create oai message to be appended to the oai conversation that can be passed to oai directly.
        self._rely_messages = []

    def append_message(self, message: Optional[Dict], role, sender: Agent) -> bool:
        """
            Put the received message content into the collective message memory
        Args:
            message:
            role:
            sender:

        Returns:

        """
        oai_message = {
            k: message[k]
            for k in (
                "content",
                "function_call",
                "name",
                "context",
                "action_report",
                "review_info",
                "current_gogal",
                "model_name",
            )
            if k in message
        }
        if "content" not in oai_message:
            if "function_call" in oai_message:
                oai_message[
                    "content"
                ] = None  # if only function_call is provided, content will be set to None.
            else:
                return False
        oai_message["role"] = "function" if message.get("role") == "function" else role
        if "function_call" in oai_message:
            oai_message[
                "role"
            ] = "assistant"  # only messages with role 'assistant' can have a function call.
            oai_message["function_call"] = dict(oai_message["function_call"])

        gpts_message: GptsMessage = GptsMessage(
            conv_id=self.agent_context.conv_id,
            team_mode=self.agent_context.team_mode,
            sender=sender.name,
            receiver=self.name,
            role=role,
            rounds=self.consecutive_auto_reply_counter,
            current_gogal=oai_message.get("current_gogal", None),
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

    async def a_send(
        self,
        message: Optional[Dict],
        recipient: Agent,
        reviewer: "Agent",
        request_reply: Optional[bool] = True,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
    ):
        await recipient.a_receive(
            message=message,
            sender=self,
            reviewer=reviewer,
            request_reply=request_reply,
            silent=silent,
            is_recovery=is_recovery,
        )

    async def a_receive(
        self,
        message: Optional[Dict],
        sender: Agent,
        reviewer: "Agent",
        request_reply: Optional[bool] = True,
        silent: Optional[bool] = False,
        is_recovery: Optional[bool] = False,
    ):
        if not is_recovery:
            self.consecutive_auto_reply_counter = (
                sender.consecutive_auto_reply_counter + 1
            )
            self.process_received_message(message, sender, silent)
        else:
            logger.info("Process received retrying")
            self.consecutive_auto_reply_counter = sender.consecutive_auto_reply_counter
        if request_reply is False or request_reply is None:
            logger.info("Messages that do not require a reply")
            return
        if self.is_termination_msg(message):
            logger.info(f"TERMINATE!")
            return

        verify_paas, reply = await self.a_generate_reply(
            message=message, sender=sender, reviewer=reviewer, silent=silent
        )
        if verify_paas:
            await self.a_send(
                message=reply, recipient=sender, reviewer=reviewer, silent=silent
            )
        else:
            # Exit after the maximum number of rounds of self-optimization
            if self.current_retry_counter >= self.max_retry_count:
                # If the maximum number of retries is exceeded, the abnormal answer will be returned directly.
                logger.warning(
                    f"More than {self.current_retry_counter} times and still no valid answer is output."
                )
                reply[
                    "content"
                ] = f"After trying {self.current_retry_counter} times, I still can't generate a valid answer. The current problem is:{reply['content']}!"
                reply["is_termination"] = True
                await self.a_send(
                    message=reply, recipient=sender, reviewer=reviewer, silent=silent
                )
                # raise ValueError(
                #     f"After {self.current_retry_counter} rounds of re-optimization, we still cannot get an effective answer."
                # )
            else:
                self.current_retry_counter += 1
                logger.info(
                    "The generated answer failed to verify, so send it to yourself for optimization."
                )
                await sender.a_send(
                    message=reply, recipient=self, reviewer=reviewer, silent=silent
                )

    async def a_notification(
        self,
        message: Union[Dict, str],
        recipient: Agent,
    ):
        recipient.process_received_message(message, self)

    def _print_received_message(self, message: Union[Dict, str], sender: Agent):
        # print the message received
        print(
            colored(sender.name, "yellow"),
            "(to",
            f"{self.name})-[{message.get('model_name', '')}]:\n",
            flush=True,
        )
        message = self._message_to_dict(message)

        if message.get("role") == "function":
            func_print = (
                f"***** Response from calling function \"{message['name']}\" *****"
            )
            print(colored(func_print, "green"), flush=True)
            print(message["content"], flush=True)
            print(colored("*" * len(func_print), "green"), flush=True)
        else:
            content = json.dumps(message.get("content"), ensure_ascii=False)
            if content is not None:
                if "context" in message:
                    content = AIWrapper.instantiate(
                        content,
                        message["context"],
                        self.agent_context.allow_format_str_template,
                    )
                print(content, flush=True)
            if "function_call" in message:
                function_call = dict(message["function_call"])
                func_print = f"***** Suggested function Call: {function_call.get('name', '(No function name found)')} *****"
                print(colored(func_print, "green"), flush=True)
                print(
                    "Arguments: \n",
                    function_call.get("arguments", "(No arguments found)"),
                    flush=True,
                    sep="",
                )
                print(colored("*" * len(func_print), "green"), flush=True)

            review_info = message.get("review_info", None)
            if review_info:
                approve_print = f">>>>>>>>{sender.name} Review info: \n {'Pass' if review_info.get('approve') else 'Reject'}.{review_info.get('comments')}"
                print(colored(approve_print, "green"), flush=True)

            action_report = message.get("action_report", None)
            if action_report:
                action_print = f">>>>>>>>{sender.name} Action report: \n{'execution succeeded' if action_report['is_exe_success'] else 'execution failed'},\n{action_report['content']}"
                print(colored(action_print, "blue"), flush=True)
        print("\n", "-" * 80, flush=True, sep="")

    def process_received_message(self, message, sender, silent):
        message = self._message_to_dict(message)
        # When the agent receives a message, the role of the message is "user". (If 'role' exists and is 'function', it will remain unchanged.)
        valid = self.append_message(message, None, sender)
        if not valid:
            raise ValueError(
                "Received message can't be converted into a valid ChatCompletion message. Either content or function_call must be provided."
            )
        if not silent:
            self._print_received_message(message, sender)

    async def a_review(self, message: Union[Dict, str], censored: "Agent"):
        return True, None

    def _process_action_reply(self, action_reply: Optional[Union[str, Dict, None]]):
        if isinstance(action_reply, str):
            return {"is_exe_success": True, "content": action_reply}
        elif isinstance(action_reply, dict):
            return action_reply
        elif action_reply is None:
            return None
        else:
            return dict(action_reply)

    def _gpts_message_to_ai_message(
        self, gpts_messages: Optional[List[GptsMessage]]
    ) -> List[Dict]:
        oai_messages: List[Dict] = []
        # Based on the current agent, all messages received are user, and all messages sent are assistant.
        for item in gpts_messages:
            role = ""
            if item.role:
                role = role
            else:
                if item.receiver == self.name:
                    role = ModelMessageRoleType.HUMAN
                elif item.sender == self.name:
                    role = ModelMessageRoleType.AI
                else:
                    continue
            oai_messages.append(
                {
                    "content": item.content,
                    "role": role,
                    "context": json.loads(item.context)
                    if item.context is not None
                    else None,
                    "review_info": json.loads(item.review_info)
                    if item.review_info is not None
                    else None,
                    "action_report": json.loads(item.action_report)
                    if item.action_report is not None
                    else None,
                }
            )
        return oai_messages

    def process_now_message(
        self,
        current_message: Optional[Dict],
        sender,
        rely_messages: Optional[List[Dict]] = None,
    ):
        current_gogal = current_message.get("current_gogal", None)
        ### Convert and tailor the information in collective memory into contextual memory available to the current Agent
        current_gogal_messages = self._gpts_message_to_ai_message(
            self.memory.message_memory.get_between_agents(
                self.agent_context.conv_id, self.name, sender.name, current_gogal
            )
        )
        if current_gogal_messages is None or len(current_gogal_messages) <= 0:
            current_message["role"] = ModelMessageRoleType.HUMAN
            current_gogal_messages = [current_message]
        ### relay messages
        cut_messages = []
        if rely_messages:
            for rely_message in rely_messages:
                action_report = rely_message.get("action_report", None)
                if action_report:
                    rely_message["content"] = action_report["content"]
            cut_messages.extend(rely_messages)
        else:
            cut_messages.extend(self._rely_messages)

        if len(current_gogal_messages) < self.dialogue_memory_rounds:
            cut_messages.extend(current_gogal_messages)
        else:
            # TODO: allocate historical information based on token budget
            cut_messages.extend(current_gogal_messages[:2])
            # end_round = self.dialogue_memory_rounds - 2
            cut_messages.extend(current_gogal_messages[-3:])
        return cut_messages

    async def a_system_fill_param(self):
        self.update_system_message(self.DEFAULT_SYSTEM_MESSAGE)

    async def a_generate_reply(
        self,
        message: Optional[Dict],
        sender: Agent,
        reviewer: Agent,
        silent: Optional[bool] = False,
        rely_messages: Optional[List[Dict]] = None,
    ):
        ## 0.New message build
        new_message = {}
        new_message["context"] = message.get("context", None)
        new_message["current_gogal"] = message.get("current_gogal", None)

        ## 1.LLM Reasonging
        await self.a_system_fill_param()
        current_messages = self.process_now_message(message, sender, rely_messages)
        ai_reply, model = await self.a_reasoning_reply(messages=current_messages)
        new_message["content"] = ai_reply
        new_message["model_name"] = model
        ## 2.Review of reasoning results
        approve = True
        comments = None
        if reviewer and ai_reply:
            approve, comments = await reviewer.a_review(ai_reply, self)
        new_message["review_info"] = {"approve": approve, "comments": comments}
        ## 3.reasoning result action
        if approve:
            excute_reply = await self.a_action_reply(
                message=ai_reply,
                sender=sender,
                reviewer=reviewer,
            )
            new_message["action_report"] = self._process_action_reply(excute_reply)
        ## 4.verify reply
        return await self.a_verify_reply(new_message, sender, reviewer)

    async def a_verify(self, message: Optional[Dict]):
        return True, message

    async def _optimization_check(self, message: Optional[Dict]):
        need_retry = False
        fail_reason = ""
        ## Check approval results
        if "review_info" in message:
            review_info = message.get("review_info")
            if review_info and not review_info.get("approve"):
                fail_reason = review_info.get("comments")
                need_retry = True
        ## Check execution results
        if "action_report" in message and not need_retry:
            action_report = message["action_report"]
            if action_report:
                if not action_report["is_exe_success"]:
                    fail_reason = action_report["content"]
                    need_retry = True
                else:
                    if (
                        not action_report["content"]
                        or len(action_report["content"].strip()) < 1
                    ):
                        fail_reason = f'The code is executed successfully but the output:{action_report["content"]} is invalid or empty. Please reanalyze the target to generate valid code.'
                        need_retry = True
        ##  Verify the correctness of the results
        if not need_retry:
            verify_pass, verfiy_msg = await self.a_verify(message)
            if not verify_pass:
                need_retry = True
                fail_reason = verfiy_msg
        return need_retry, fail_reason

    async def a_verify_reply(
        self, message: Optional[Dict], sender: "Agent", reviewer: "Agent", **kwargs
    ) -> Union[str, Dict, None]:
        need_retry, fail_reason = await self._optimization_check(message)
        if need_retry:
            ## Before optimization, wrong answers are stored in memory
            await self.a_send(
                message=message,
                recipient=sender,
                reviewer=reviewer,
                request_reply=False,
            )
            ## Send error messages to yourself for retrieval optimization and increase the number of retrievals
            retry_message = {}
            retry_message["context"] = message.get("context", None)
            retry_message["current_gogal"] = message.get("current_gogal", None)
            retry_message["model_name"] = message.get("model_name", None)
            retry_message["content"] = fail_reason
            ## Use the original sender to send the retry message to yourself
            return False, retry_message
        else:
            ## The verification passes, the message is released, and the number of retries returns to 0.
            self.current_retry_counter = 0
            return True, message

    async def a_retry_chat(
        self,
        recipient: "ConversableAgent",
        reviewer: "Agent" = None,
        clear_history: Optional[bool] = True,
        silent: Optional[bool] = False,
        **context,
    ):
        last_message: GptsMessage = self.memory.message_memory.get_last_message(
            self.agent_context.conv_id
        )
        self.consecutive_auto_reply_counter = last_message.rounds
        message = {
            "content": last_message.content,
            "context": json.loads(last_message.context)
            if last_message.context
            else None,
            "current_gogal": last_message.current_gogal,
            "review_info": json.loads(last_message.review_info)
            if last_message.review_info
            else None,
            "action_report": json.loads(last_message.action_report)
            if last_message.action_report
            else None,
            "model_name": last_message.model_name,
        }
        await self.a_send(
            message,
            recipient,
            reviewer,
            request_reply=True,
            silent=silent,
            is_recovery=True,
        )

    async def a_initiate_chat(
        self,
        recipient: "ConversableAgent",
        reviewer: "Agent" = None,
        clear_history: Optional[bool] = True,
        silent: Optional[bool] = False,
        **context,
    ):
        await self.a_send(
            {
                "content": self.generate_init_message(**context),
            },
            recipient,
            reviewer,
            request_reply=True,
            silent=silent,
        )

    def reset(self):
        """Reset the agent."""
        self.clear_history()
        self.reset_consecutive_auto_reply_counter()

        for reply_func_tuple in self._reply_func_list:
            if reply_func_tuple["reset_config"] is not None:
                reply_func_tuple["reset_config"](reply_func_tuple["config"])
            else:
                reply_func_tuple["config"] = copy.copy(reply_func_tuple["init_config"])

    def reset_consecutive_auto_reply_counter(self):
        """Reset the consecutive_auto_reply_counter of the sender."""
        self.consecutive_auto_reply_counter = 0

    def clear_history(self, agent: Optional[Agent] = None):
        """Clear the chat history of the agent.

        Args:
            agent: the agent with whom the chat history to clear. If None, clear the chat history with all agents.
        """
        pass

    def _get_model_priority(self):
        llm_models_priority = self.agent_context.model_priority
        if llm_models_priority:
            if self.name in llm_models_priority:
                model_priority = llm_models_priority[self.name]
            else:
                model_priority = llm_models_priority["default"]
            return model_priority
        else:
            return None

    def _filter_health_models(self, need_uses: Optional[list]):
        all_modes = self.agent_context.llm_models
        can_uses = []
        for item in all_modes:
            if item.model in need_uses:
                can_uses.append(item)
        return can_uses

    def _select_llm_model(self, old_model: str = None):
        """
        LLM model selector, currently only supports manual selection, more strategies will be opened in the future
        Returns:
        """
        all_modes = self.agent_context.llm_models
        model_priority = self._get_model_priority()
        if model_priority and len(model_priority) > 0:
            can_uses = self._filter_health_models(model_priority)
            if len(can_uses) > 0:
                return can_uses[0].model

        now_model = all_modes[0]
        if old_model:
            filtered_list = [item for item in all_modes if item.model != old_model]
            if filtered_list and len(filtered_list) >= 1:
                now_model = filtered_list[0]
        return now_model.model

    async def a_reasoning_reply(
        self, messages: Optional[List[Dict]] = None
    ) -> Union[str, Dict, None]:
        """(async) Reply based on the conversation history and the sender.
        Args:
            messages: a list of messages in the conversation history.
            default_reply (str or dict): default reply.
            sender: sender of an Agent instance.
            exclude: a list of functions to exclude.

        Returns:
            str or dict or None: reply. None if no reply is generated.
        """
        last_model = None
        last_err = None
        retry_count = 0
        while retry_count < 3:
            llm_model = self._select_llm_model(last_model)
            try:
                response = await self.client.create(
                    context=messages[-1].pop("context", None),
                    messages=self._oai_system_message + messages,
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
                await asyncio.sleep(15)  ## TODO，Rate limit reached for gpt-3.5-turbo

        if last_err:
            raise ValueError(last_err)

    async def a_action_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: "Agent" = None,
        exclude: Optional[List[Callable]] = None,
        **kwargs,
    ) -> Union[str, Dict, None]:
        for reply_func_tuple in self._reply_func_list:
            reply_func = reply_func_tuple["reply_func"]
            if exclude and reply_func in exclude:
                continue
            if self._match_trigger(reply_func_tuple["trigger"], sender):
                if asyncio.coroutines.iscoroutinefunction(reply_func):
                    final, reply = await reply_func(
                        self,
                        message=message,
                        sender=sender,
                        reviewer=reviewer,
                        config=reply_func_tuple["config"],
                    )
                else:
                    final, reply = reply_func(
                        self,
                        message=message,
                        sender=sender,
                        reviewer=reviewer,
                        config=reply_func_tuple["config"],
                    )
                if final:
                    return reply
        return self._default_auto_reply

    def _match_trigger(self, trigger, sender):
        """Check if the sender matches the trigger."""
        if trigger is None:
            return sender is None
        elif isinstance(trigger, str):
            return trigger == sender.name
        elif isinstance(trigger, type):
            return isinstance(sender, trigger)
        elif isinstance(trigger, Agent):
            return trigger == sender
        elif isinstance(trigger, Callable):
            return trigger(sender)
        elif isinstance(trigger, list):
            return any(self._match_trigger(t, sender) for t in trigger)
        else:
            raise ValueError(f"Unsupported trigger type: {type(trigger)}")

    def generate_init_message(self, **context) -> Union[str, Dict]:
        """Generate the initial message for the agent.

        Override this function to customize the initial message based on user's request.
        If not overridden, "message" needs to be provided in the context.
        """
        return context["message"]
