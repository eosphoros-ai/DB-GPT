"""Indicator Agent."""

import logging

from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from ..expand.actions.indicator_action import IndicatorAction

logger = logging.getLogger()

CHECK_RESULT_SYSTEM_MESSAGE = """
You are an expert in analyzing the results of a summary task.
Your responsibility is to check whether the summary results can summarize the input provided by the user, and then make a judgment. You need to answer according to the following rules: 
    Rule 1: If you think the summary results can summarize the input provided by the user, only return True.
    Rule 2: If you think the summary results can NOT summarize the input provided by the user, return False and the reason, splitted by | and ended by TERMINATE. For instance: False|Some important concepts in the input are not summarized. TERMINATE
"""  # noqa


class IndicatorAssistantAgent(ConversableAgent):
    """IndicatorAssistantAgent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "Indicator",
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "Indicator",
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "Summarize answer summaries based on user questions from provided resource information or from historical conversation memories.",  # noqa
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Prioritize the summary of answers to user questions from the improved resource text. If no relevant information is found, summarize it from the historical dialogue memory given. It is forbidden to make up your own.",  # noqa
                "You need to first detect user's question that you need to answer with your summarization.",  # noqa
                "Extract the provided text content used for summarization.",
                "Then you need to summarize the extracted text content.",
                "Output the content of summarization ONLY related to user's question. The output language must be the same to user's question language.",  # noqa
                """If you think the provided text content is not related to user questions at all, ONLY output "Did not find the information you want."!!.""",  # noqa
            ],
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "You can summarize provided text content according to user's questions and output the summaraization.",  # noqa
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_desc",
        ),
    )
    max_retry_count: int = 3

    def __init__(self, **kwargs):
        """Init indicator AssistantAgent."""
        super().__init__(**kwargs)

        self._init_actions([IndicatorAction])
