from typing import Callable, Dict, Literal, Optional, Union

from dbgpt._private.config import Config
from dbgpt.agent.agents.base_agent import ConversableAgent
from dbgpt.agent.plugin.commands.command_mange import ApiCall

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext


class RetrieveSummaryAssistantAgent(ConversableAgent):
    """(In preview) Assistant agent, designed to solve a task with LLM.

    AssistantAgent is a subclass of ConversableAgent configured with a default system message.
    The default system message is designed to solve a task with LLM,
    including suggesting python code blocks and debugging.
    `human_input_mode` is default to "NEVER"
    and `code_execution_config` is default to False.
    This agent doesn't execute code by default, and expects the user to execute the code.
    """

    # TODO: Write a new default system message. This message is copied from AutoGen
    DEFAULT_SYSTEM_MESSAGE = """You're a retrieve augmented chatbot. You answer user's questions based on your own knowledge and the
        context provided by the user.
        If you can't answer the question with or without the current context, you should reply exactly `UPDATE CONTEXT`.
        You must give as short an answer as possible.

        User's question is: {input_question}

        Context is: {input_context}
    """

    DEFAULT_DESCRIBE = """Summarize provided content according to user's questions and output the summaraization."""

    NAME = "Retrieve_Summarizer"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        describe: Optional[str] = DEFAULT_DESCRIBE,
        is_termination_msg: Optional[Callable[[Dict], bool]] = None,
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
        self.register_reply(Agent, RetrieveSummaryAssistantAgent.generate_summary_reply)
        self.agent_context = agent_context

    async def generate_retrieve_summary_reply(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Optional[Agent] = None,
        config: Optional[Union[Dict, Literal[False]]] = None,
    ):
        """Generate a reply with summary."""

        # TODO: 
        # 1. Extract User Question from massage
        # 2. Extract file / webpage list from message
        # 3. Summarize each chunk
        # 4. Combine summarization of each chunk
        summary_result = ""
        response_success = True
        view = None
        content = None
        if message is None:
            # Answer failed, turn on automatic repair
            fail_reason += f"Nothing is summarized, please check your input."
            response_success = False
        else:
            try:
                vis_client = ApiCall()
                content = summary_result
                view = summary_result
            except Exception as e:
                fail_reason += f"Return summarization error，{str(e)}"
                response_success = False

        if not response_success:
            content = fail_reason
        return True, {
            "is_exe_success": response_success,
            "content": content,
            "view": view,
        }

    async def _extract_user_question(
        self,
        message: Optional[str] = None
    ):
        pass

    async def _extract_knowledge_content(
        self,
        message: Optional[str] = None,
        chunk_size: Optional[int] = None
    ):
        pass
