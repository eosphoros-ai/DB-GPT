from pilot.dbgpts.agents.conversable_agent import ConversableAgent
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Type, Union
from pilot.common.code_utils import (
    UNKNOWN,
    execute_code,
    extract_code,
    infer_lang,
)
from .agent import Agent
try:
    from termcolor import colored
except ImportError:

    def colored(x, *args, **kwargs):
        return x

class AssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """You are a helpful AI assistant.
    """

    def __init__(
        self,
        name: str,
        describe: Optional[str],
        system_message: Optional[str] = DEFAULT_SYSTEM_MESSAGE,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        agent_context: 'AgentContext' = None,
        **kwargs,
    ):
        super().__init__(
            name,
            describe,
            system_message,
            is_termination_msg,
            max_consecutive_auto_reply,
            human_input_mode,
            agent_context,
            **kwargs,
        )
