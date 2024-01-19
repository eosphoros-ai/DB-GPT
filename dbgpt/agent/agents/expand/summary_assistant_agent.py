import logging
from typing import Callable, Dict, Literal, Optional, Union

from dbgpt.agent.agents.base_agent import ConversableAgent
from dbgpt.core.interface.message import ModelMessageRoleType

from ...memory.gpts_memory import GptsMemory
from ..agent import Agent, AgentContext

logger = logging.getLogger()


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

    CHECK_RESULT_SYSTEM_MESSAGE = f"""
    You are an expert in analyzing the results of a summary task.
    Your responsibility is to check whether the summary results can summarize the input provided by the user, and then make a judgment. You need to answer according to the following rules:
        Rule 1: If you think the summary results can summarize the input provided by the user, only return True.
        Rule 2: If you think the summary results can NOT summarize the input provided by the user, return False and the reason, splitted by | and ended by TERMINATE. For instance: False|Some important concepts in the input are not summarized. TERMINATE
    """

    DEFAULT_DESCRIBE = """Summarize provided text content according to user's questions and output the summaraization."""

    NAME = "Summarizer"

    def __init__(
        self,
        memory: GptsMemory,
        agent_context: AgentContext,
        describe: Optional[str] = DEFAULT_DESCRIBE,
        max_consecutive_auto_reply: Optional[int] = None,
        human_input_mode: Optional[str] = "NEVER",
        **kwargs,
    ):
        super().__init__(
            name=self.NAME,
            memory=memory,
            describe=describe,
            system_message=self.DEFAULT_SYSTEM_MESSAGE,
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

    async def a_verify(self, message: Optional[Dict]):
        self.update_system_message(self.CHECK_RESULT_SYSTEM_MESSAGE)
        current_goal = message.get("current_gogal", None)
        action_report = message.get("action_report", None)
        task_result = ""
        if action_report:
            task_result = action_report.get("content", "")

        check_result, model = await self.a_reasoning_reply(
            [
                {
                    "role": ModelMessageRoleType.HUMAN,
                    "content": f"""Please understand the following user input and summary results and give your judgment:
                        User Input: {current_goal}
                        Summary Results: {task_result}
                    """,
                }
            ]
        )

        fail_reason = ""
        if "True" in check_result:
            success = True
        else:
            success = False
            try:
                _, fail_reason = check_result.split("|")
                fail_reason = f"The summary results cannot summarize the user input due to: {fail_reason}. Please re-understand and complete the summary task."
            except:
                logger.warning(
                    f"The model thought the results are irrelevant but did not give the correct format of results."
                )
                fail_reason = "The summary results cannot summarize the user input. Please re-understand and complete the summary task."
        return success, fail_reason
