import asyncio
from collections import defaultdict
import copy
import json
import logging
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from dbgpt.agent.agents.agent import Agent, AgentContext
from dbgpt.agent.agents.llm_client import AIWrapper
from dbgpt.agent.memory.gpts_memory import GptsMemory
from dbgpt.agent.memory.base import GptsMessage
from dbgpt.util.error_types import LLMChatError
from dbgpt.core.interface.message import ModelMessageRoleType

try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x

logger = logging.getLogger(__name__)


class ConversableAgent(Agent):


    MAX_CONSECUTIVE_AUTO_REPLY = 100  # maximum number of consecutive auto replies (subject to future change)

    def __init__(
            self,
            name: str,
            memory: GptsMemory,
            model_priority: Optional[List[str]] = None,
            describe: Optional[str] = "You are a helpful AI Assistant.",
            system_message: Optional[str] = "You are a helpful AI Assistant.",
            is_termination_msg: Optional[Callable[[Dict], bool]] = None,
            max_consecutive_auto_reply: Optional[int] = None,
            human_input_mode: Optional[str] = "TERMINATE",
            agent_context: Optional[AgentContext] = None,
            default_auto_reply: Optional[Union[str, Dict, None]] = "",
    ):

        super().__init__(name, memory, describe)

        # a dictionary of conversations, default value is list
        # self._oai_messages = defaultdict(list)
        self._oai_system_message = [{"content": system_message, "role": ModelMessageRoleType.SYSTEM}]
        self._rely_messages = []
        self._is_termination_msg = (
            is_termination_msg
            if is_termination_msg is not None
            else (lambda x: x.get("content") == "TERMINATE")
        )


        self.client = AIWrapper()

        self.model_priority = model_priority
        self.human_input_mode = human_input_mode
        self._max_consecutive_auto_reply = (
            max_consecutive_auto_reply
            if max_consecutive_auto_reply is not None
            else self.MAX_CONSECUTIVE_AUTO_REPLY
        )
        self.consecutive_auto_reply_counter: int = 0

        ## By default, the memory of 4 rounds of dialogue is retained.
        self.dialogue_memory_rounds = 5
        self._default_auto_reply = default_auto_reply
        self._reply_func_list = []

        self.agent_context: AgentContext = agent_context



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
    def chat_messages(self) -> Dict[Agent, List[Dict]]:
        """A dictionary of conversations from agent to list of messages."""
        all_gpts_messages = self.memory.message_memory.get_by_agent(self.agent_context.conv_id, self.name)
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

        agent_messages = self.memory.message_memory.get_between_agents(self.agent_context.conv_id, self.name, agent.name)
        if len(agent_messages) <=0:
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

    def append_rely_message(self, message: Optional[Dict], role)->bool:
        message = self._message_to_dict(message)
        message["role"] = role
        # create oai message to be appended to the oai conversation that can be passed to oai directly.
        self._rely_messages.append(message)

    def reset_rely_message(self)->bool:
        # create oai message to be appended to the oai conversation that can be passed to oai directly.
        self._rely_messages = []

    def append_message(self, message: Optional[Dict], role, sender: Agent)->bool:
        """
            Put the received message content into the collective message memory
        Args:
            conv_id:
            message:
            role:
            sender:

        Returns:

        """
        oai_message = {
            k: message[k]
            for k in ("content", "function_call", "name", "context", "action_report", "review_info", "current_gogal", "model_name")
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
            conv_id= self.agent_context.conv_id,
            sender= sender.name,
            receiver=self.name,
            role=role,
            rounds= self.consecutive_auto_reply_counter,
            current_gogal=oai_message['current_gogal'],
            content=oai_message['content'],
            context= json.dumps(oai_message['context']) if 'context' in oai_message else None,
            review_info= json.dumps(oai_message['review_info']) if 'review_info' in oai_message else None,
            action_report= json.dumps(oai_message['action_report']) if 'action_report' in oai_message else None,
            model_name= oai_message.get("model_name", None)
        )


        self.memory.message_memory.append(gpts_message)
        return True

    async def a_send(
            self,
            message: Optional[Dict],
            recipient: Agent,
            reviewer: "Agent",
            request_reply: Optional[bool] = None,
            silent: Optional[bool] = False,
    ):
        await recipient.a_receive(message=message, sender=self, reviewer=reviewer, request_reply=request_reply,
                                  silent=silent)

    def _print_received_message(self, message: Union[Dict, str], sender: Agent):
        # print the message received
        print(colored(sender.name, "yellow"), "(to", f"{self.name})-[{message.get('model_name', '')}]:\n", flush=True)
        message = self._message_to_dict(message)

        if message.get("role") == "function":
            func_print = (
                f"***** Response from calling function \"{message['name']}\" *****"
            )
            print(colored(func_print, "green"), flush=True)
            print(message["content"], flush=True)
            print(colored("*" * len(func_print), "green"), flush=True)
        else:
            content = json.dumps(message.get("content"))
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
            if "review_info" in message:
                review_info = dict(message["review_info"])
                approve_print = f"***** Review results: {'Pass' if review_info.get('approve') else 'Reject'}.{review_info.get('comments')}"
                print(colored(approve_print, "green"), flush=True)

            if "action_report" in message:
                action_report = dict(message['action_report'])
                action_print = f">>>>>>>>{self.name} Action report: \n execution result:{'execution succeeded' if action_report['is_exe_success'] else 'execution failed'},\noutput:{action_report['content']}"
                print(colored(action_print, "blue"), flush=True)
        print("\n", "-" * 80, flush=True, sep="")



    def _process_received_message(self, message, sender, silent):
        message = self._message_to_dict(message)
        # When the agent receives a message, the role of the message is "user". (If 'role' exists and is 'function', it will remain unchanged.)
        valid = self.append_message(message, None, sender)
        if not valid:
            raise ValueError("Received message can't be converted into a valid ChatCompletion message. Either content or function_call must be provided.")
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

    def _gpts_message_to_ai_message(self, gpts_messages:List[GptsMessage])->List[Dict]:
        oai_messages: list[dict] = []
        ###Based on the current agent, all messages received are user, and all messages sent are assistant.
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
            oai_messages.append({
                "content": item.content,
                "role": role,
                "context": json.loads(item.context) if item.context is not None else None,
                "review_info": json.loads(item.review_info) if item.review_info is not None else None,
                "action_report": json.loads(item.action_report) if item.action_report is not None else None,
            })
        return oai_messages



    def process_now_message(self, sender, current_gogal:Optional[str] = None):
        ### Convert and tailor the information in collective memory into contextual memory available to the current Agent
        current_gogal_messages = self._gpts_message_to_ai_message(self.memory.message_memory.get_between_agents(self.agent_context.conv_id, self.name, sender.name, current_gogal))

        ### relay messages
        cut_messages = []
        cut_messages.extend(self._rely_messages)

        if len(current_gogal_messages) < self.dialogue_memory_rounds:
            cut_messages.extend(current_gogal_messages)
        else:
            ### TODO 基于token预算来分配历史信息
            cut_messages.extend(current_gogal_messages[:2])
            # end_round = self.dialogue_memory_rounds - 2
            cut_messages.extend(current_gogal_messages[-3:])
        return cut_messages


    async def a_reply(self,
                      message: Optional[Dict],
                      sender: Agent,
                      reviewer: "Agent",
                      silent: Optional[bool] = False,
                      ):
        new_message = {}
        new_message['content'] = message.get('content', None)
        new_message['context'] = message.get('context', None)
        new_message['current_gogal'] = message.get('current_gogal', None)
        need_retry = False
        if "review_info" in message:
            review_info = message.get('review_info')
            if review_info and not review_info.get('approve'):
                new_message['content'] =  review_info.get('comments')
                need_retry = True

        if "action_report" in message and not need_retry:
            action_report = message['action_report']
            if action_report:
                new_message['content'] = action_report["content"]
                if not action_report['is_exe_success']:
                    need_retry = True

        if need_retry:
            return await self.a_send(new_message, sender, reviewer, request_reply=True, silent=silent)
        else:

            ai_reply, model = await self.a_reasoning_reply(messages=self.process_now_message(sender,  new_message['current_gogal']), sender=sender, reviewer=reviewer)
            ###Each reply is sent to the reviewer for decision-making
            approve = True
            comments = None
            if reviewer and ai_reply:
                approve, comments = await reviewer.a_review(ai_reply, self)

            if approve:
                excute_reply = await self.a_action_reply(
                    message=ai_reply,
                    sender=sender,
                    reviewer=reviewer,

                )
                new_message['content'] = ai_reply
                new_message['action_report'] = self._process_action_reply(excute_reply)
                new_message['model_name'] = model
                passed, err_info = await self.a_verify_reply(action_reply=excute_reply, sender=sender)
                if not passed:
                    new_message['review_info'] = {
                        "approve": False,
                        "comments": err_info
                    }
                else:
                    new_message['review_info']={
                            "approve": approve,
                            "comments": comments
                        }
            await self.a_send(new_message, sender, reviewer, request_reply=True, silent=silent)

    async def a_receive(
            self,
            message: Optional[Dict],
            sender: Agent,
            reviewer: "Agent",
            request_reply: Optional[bool] = None,
            silent: Optional[bool] = False,
    ):
        self.consecutive_auto_reply_counter = sender.consecutive_auto_reply_counter + 1
        self._process_received_message(message, sender, silent)

        if (
                request_reply is False
                or request_reply is None

        ):
            logger.info("Messages that do not require a reply")
            return

        await asyncio.sleep(20)  ##TODO  Rate limit reached for gpt-3.5-turbo
        await self.a_reply(message=message, sender=sender, reviewer=reviewer, silent=silent)

    async def a_verify_reply(self, action_reply: Optional[Dict], sender: "Agent", **kwargs) -> Union[str, Dict, None]:
        return True, None

    def _prepare_chat(self, recipient, clear_history):
        self.reset_consecutive_auto_reply_counter()

        if clear_history:
            self.clear_history(recipient)
            recipient.clear_history(self)

    async def a_retry_chat(
            self,
            recipient: "ConversableAgent",
            agent_map: dict,
            reviewer: "Agent" = None,
            clear_history: Optional[bool] = True,
            silent: Optional[bool] = False,
            **context
    ):
        last_message: GptsMessage = self.memory.message_memory.get_last_message(self.agent_context.conv_id)
        sender = agent_map[last_message.sender]
        receiver = agent_map[last_message.receiver]

        await  receiver.a_retry(sender=sender, reviewer=self, last_message= last_message)


    async def a_retry(self, sender: Agent, reviewer: Agent, last_message:GptsMessage):
        self.consecutive_auto_reply_counter = last_message.rounds
        await self.a_reply(message={
            "content": last_message.content,
            "context": json.loads(last_message.context) if last_message.context else None,
            "current_gogal": last_message.current_gogal,
            "review_info": json.loads(last_message.review_info) if last_message.review_info else None,
            "action_report": json.loads(last_message.action_report) if last_message.action_report else None,
            "model_name": last_message.model_name
        }, sender=sender, reviewer=reviewer)


    async def a_initiate_chat(
            self,
            recipient: "ConversableAgent",
            reviewer: "Agent" = None,
            clear_history: Optional[bool] = True,
            silent: Optional[bool] = False,
            **context,
    ):

        self._prepare_chat(recipient, clear_history)
        await self.a_send({"content": self.generate_init_message(**context), "current_gogal": self.generate_init_message(**context)}, recipient, reviewer,request_reply=True, silent=silent)

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
        # if agent is None:
        #     self._oai_messages.clear()
        # else:
        #     self._oai_messages[agent].clear()

    def _select_llm_model(self, old_model: str = None):
        """
        LLM model selector, currently only supports manual selection, more strategies will be opened in the future
        Returns:

        """
        all_modes = self.agent_context.llm_models
        model_priority = self.model_priority
        if model_priority  and len(model_priority) >0:
            for model in model_priority:
                if old_model and model == old_model:
                    continue
                if model in all_modes:
                    return model

        if old_model:
            filtered_list = [item for item in all_modes if item != old_model]
            return filtered_list[0]
        else:
            return all_modes[0]

    async def a_generate_oai_reply(self,messages: Optional[List[Dict]], rely_infos: Optional[List[Dict]] = None) -> Tuple[bool, Union[str, Dict, None]]:
        """Generate a reply using autogen.oai."""
        last_model = None
        last_err = None
        retry_count = 0
        while retry_count < 3:
            llm_model =self._select_llm_model(last_model)
            try:
                response = await  self.client.create(
                    context=messages[-1].pop("context", None),
                    messages=self._oai_system_message + messages,
                    llm_model=llm_model,
                    max_new_tokens=self.agent_context.max_new_tokens,
                    temperature=self.agent_context.temperature
                )
                return True, response, llm_model
            except LLMChatError as e:
                logger.error(f"model:{llm_model} generate Failed!{str(e)}" )
                retry_count +=1
                last_model = llm_model
                last_err  = str(e)
        if last_err:
            raise ValueError(last_err)

    async def a_reasoning_reply(
        self,
        messages: Union[List[Dict]],
        sender: "Agent",
        reviewer: "Agent",
        request_reply: Optional[bool] = None,
        silent: Optional[bool] = False) -> Union[str, Dict, None]:
        """(async) Reply based on the conversation history and the sender.
        Args:
            messages: a list of messages in the conversation history.
            default_reply (str or dict): default reply.
            sender: sender of an Agent instance.
            exclude: a list of functions to exclude.

        Returns:
            str or dict or None: reply. None if no reply is generated.
        """

        final, reply, model = await self.a_generate_oai_reply(messages=messages)
        # if reply:
        #     self._process_generate_message(reply, self)
        return reply, model

    async def a_action_reply(self, message: Optional[str] = None,
                                      sender: Optional[Agent] = None,
                                      reviewer: "Agent" = None,
                                      exclude: Optional[List[Callable]] = None, **kwargs) -> Union[str, Dict, None]:
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
