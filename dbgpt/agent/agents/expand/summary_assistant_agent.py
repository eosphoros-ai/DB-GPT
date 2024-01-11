from typing import Callable, Dict, Literal, Optional, Union

from dbgpt.agent.agents.base_agent import ConversableAgent

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext


class SummaryAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    DEFAULT_SYSTEM_MESSAGE = """You are a great summary writter to summarize the provided text content according to user questions.
           Please complete this task step by step following instructions below:
           1. You need to first detect user's question that you need to answer with your summarization.
           2. Extract the provided text content used for summarization.
           3. Then you need to summarize the extracted text content.
           4. Output the content of summarization ONLY related to user's question. The output language must be the same to user's question language.

           ####Important Notice####
           If you think the provided text content is not related to user questions at all, ONLY output "NO RELATIONSHIP.TERMINATE."!!.
        """

    DEFAULT_DESCRIBE = """Summarize provided text content according to user's questions and output the summaraization."""

    NAME = "Summarizer"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        describe: Optional[str] = DEFAULT_DESCRIBE,
        is_termination_msg: Optional[Callable[[Dict], bool]] = lambda x: isinstance(
            x, dict
        )
        and "TERMINATE" in str(x).upper(),
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
            is_termination_msg=is_termination_msg,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            agent_context=agent_context,
            **kwargs,
        )
        self.register_reply(Agent, SummaryAssistantAgent.generate_summary_reply)
        self.agent_context = agent_context

    async def generate_summary_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply with summary."""
        fail_reason = None
        response_success = True
        view = None
        content = None
        if message is None:
            # Answer failed, turn on automatic repair
            fail_reason += f"Nothing is summarized, please check your input."
            response_success = False
        else:
            try:
                if "NO RELATIONSHIP.TERMINATE." in message:
                    fail_reason = f"Return summarization error, the provided text content has no relationship to user's question. TERMINATE."
                    response_success = False
                else:
                    content = message
                    view = content
            except Exception as e:
                fail_reason = f"Return summarization error, {str(e)}"
                response_success = False

        if not response_success:
            content = fail_reason
        return True, {
            "is_exe_success": response_success,
            "content": content,
            "view": view,
        }
