from .conversable_agent import ConversableAgent
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from .agent import Agent
from ..memory.gpts_memory import GptsMemory
try:
    from termcolor import colored
except ImportError:
    def colored(x, *args, **kwargs):
        return x

class UserProxyAgent(ConversableAgent):
    """(In preview) A proxy agent for the user, that can execute code and provide feedback to the other agents.

    """

    def __init__(
        self,
        name: str,
        describe: Optional[str],
        memory: GptsMemory,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "ALWAYS",
        agent_context: 'AgentContext' = None,
        default_auto_reply: Optional[Union[str, Dict, None]] = "",

    ):
        super().__init__(
            name,
            memory,
            describe,
            describe,
            is_termination_msg,
            max_consecutive_auto_reply,
            human_input_mode,
            agent_context,
            default_auto_reply,
        )
        self.register_reply(Agent, UserProxyAgent.check_termination_and_human_reply)

    def get_human_input(self, prompt: str) -> str:
        """Get human input.

        Override this method to customize the way to get human input.

        Args:
            prompt (str): prompt for the human input.

        Returns:
            str: human input.
        """
        reply = input(prompt)
        return reply

    async def a_generate_reply(self, messages: Optional[List[Dict]] = None, sender: Optional[Agent] = None,
                               is_plan_goals: Optional[bool] = False, ) -> Union[str, Dict, None]:

        message = messages[-1]

        if message["role"] != "function":
            message["name"] = sender.name
        return message['content']


    async def check_termination_and_human_reply(
            self,
            message: Optional[str] = None,
            sender: Optional[Agent] = None,
            reviewer: "Agent" = None,
            config: Optional[Union[Dict, Literal[False]]] = None,
    ) -> Tuple[bool, Union[str, Dict, None]]:
        """Check if the conversation should be terminated, and if human reply is provided."""
        if config is None:
            config = self
        if message is None:
            messages = self._oai_messages[sender]
            message = messages[-1].get("content", "")
        reply = ""
        no_human_input_msg = ""
        if self.human_input_mode == "ALWAYS":
            reply = self.get_human_input(
                f"Provide feedback to {sender.name}. Press enter to skip and use auto-reply, or type 'exit' to end the conversation: "
            )
            no_human_input_msg = "NO HUMAN INPUT RECEIVED." if not reply else ""
            # if the human input is empty, and the message is a termination message, then we will terminate the conversation
            reply = reply if reply or not self._is_termination_msg(message) else "exit"
        else:
            if self._consecutive_auto_reply_counter[sender] >= self._max_consecutive_auto_reply_dict[sender]:
                if self.human_input_mode == "NEVER":
                    reply = "exit"
                else:
                    # self.human_input_mode == "TERMINATE":
                    terminate = self._is_termination_msg(message)
                    reply = self.get_human_input(
                        f"Please give feedback to {sender.name}. Press enter or type 'exit' to stop the conversation: "
                        if terminate
                        else f"Please give feedback to {sender.name}. Press enter to skip and use auto-reply, or type 'exit' to stop the conversation: "
                    )
                    no_human_input_msg = "NO HUMAN INPUT RECEIVED." if not reply else ""
                    # if the human input is empty, and the message is a termination message, then we will terminate the conversation
                    reply = reply if reply or not terminate else "exit"
            elif self._is_termination_msg(message):
                if self.human_input_mode == "NEVER":
                    reply = "exit"
                else:
                    # self.human_input_mode == "TERMINATE":
                    reply = self.get_human_input(
                        f"Please give feedback to {sender.name}. Press enter or type 'exit' to stop the conversation: "
                    )
                    no_human_input_msg = "NO HUMAN INPUT RECEIVED." if not reply else ""
                    # if the human input is empty, and the message is a termination message, then we will terminate the conversation
                    reply = reply or "exit"

        # print the no_human_input_msg
        if no_human_input_msg:
            print(colored(f"\n>>>>>>>> {no_human_input_msg}", "red"), flush=True)

        # stop the conversation
        if reply == "exit":
            # reset the consecutive_auto_reply_counter
            self._consecutive_auto_reply_counter[sender] = 0
            return True, None

        # send the human reply
        if reply or self._max_consecutive_auto_reply_dict[sender] == 0:
            # reset the consecutive_auto_reply_counter
            self._consecutive_auto_reply_counter[sender] = 0
            return True, reply

        # increment the consecutive_auto_reply_counter
        self._consecutive_auto_reply_counter[sender] += 1
        if self.human_input_mode != "NEVER":
            print(colored("\n>>>>>>>> USING AUTO REPLY...", "red"), flush=True)

        return False, None