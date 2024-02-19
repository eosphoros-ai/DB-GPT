import logging
from typing import Callable, Dict, List, Literal, Optional, Union

from dbgpt.agent.actions.indicator_action import IndicatorAction
from dbgpt.agent.agents.base_agent_new import ConversableAgent

logger = logging.getLogger()

CHECK_RESULT_SYSTEM_MESSAGE = f"""
You are an expert in analyzing the results of a summary task.
Your responsibility is to check whether the summary results can summarize the input provided by the user, and then make a judgment. You need to answer according to the following rules:
    Rule 1: If you think the summary results can summarize the input provided by the user, only return True.
    Rule 2: If you think the summary results can NOT summarize the input provided by the user, return False and the reason, splitted by | and ended by TERMINATE. For instance: False|Some important concepts in the input are not summarized. TERMINATE
"""


class IndicatorAssistantAgent(ConversableAgent):
    name = "Indicator"
    profile: str = "IndicatorExpert"
    goal: str = "Extract key information based on the provided resource information, user questions and historical dialogue memory, and summarize it into standard indicator output."

    constraints: List[str] = [
        "The parameters, API, and request methods collected according to the given structure will be automatically executed as the indicator interface. Please ensure that the data has been mentioned in the conversation. It is prohibited to make up your own.",
        "You need to first detect user's question that you need to answer with your summarization.",
        "Extract the provided text content used for summarization,Then you need to summarize the extracted text content.",
        "When completing the current goal, please refer to the user's question and the information provided. The user question is: {user_question}",
    ]
    desc: str = "Execution metrics API based on knowledge, conversation records, and user questions."
    max_retry_count: int = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_actions([IndicatorAction])

    def _init_reply_message(self, recive_message):
        reply_message = super()._init_reply_message(recive_message)
        reply_message["context"] = {
            "user_question": recive_message["current_gogal"],
        }
        return reply_message
