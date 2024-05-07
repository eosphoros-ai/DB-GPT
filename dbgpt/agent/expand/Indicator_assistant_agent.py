"""Indicator Assistant Agent."""

import logging

from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from .actions.indicator_action import IndicatorAction

logger = logging.getLogger(__name__)


class IndicatorAssistantAgent(ConversableAgent):
    """Indicator Assistant Agent."""

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
            "Summarize answer summaries based on user questions from provided "
            "resource information or from historical conversation memories.",
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Prioritize the summary of answers to user questions from the "
                "improved resource text. If no relevant information is found, "
                "summarize it from the historical dialogue memory given. It is "
                "forbidden to make up your own.",
                "You need to first detect user's question that you need to answer "
                "with your summarization.",
                "Extract the provided text content used for summarization.",
                "Then you need to summarize the extracted text content.",
                "Output the content of summarization ONLY related to user's question. "
                "The output language must be the same to user's question language.",
                "If you think the provided text content is not related to user "
                "questions at all, ONLY output 'Did not find the information you "
                "want.'!!.",
            ],
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_constraints",
        ),
        desc=DynConfig(
            "You can summarize provided text content according to user's questions "
            "and output the summarization.",
            category="agent",
            key="dbgpt_agent_expand_indicator_assistant_agent_profile_desc",
        ),
    )

    def __init__(self, **kwargs):
        """Create a new instance."""
        super().__init__(**kwargs)
        self._init_actions([IndicatorAction])
