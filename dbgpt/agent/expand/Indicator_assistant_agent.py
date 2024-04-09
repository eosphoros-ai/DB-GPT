"""Indicator Assistant Agent."""
import logging
from typing import List

from ..actions.indicator_action import IndicatorAction
from ..core.base_agent import ConversableAgent

logger = logging.getLogger(__name__)


class IndicatorAssistantAgent(ConversableAgent):
    """Indicator Assistant Agent."""

    name = "Indicator"
    profile: str = "Indicator"
    goal: str = (
        "Summarize answer summaries based on user questions from provided "
        "resource information or from historical conversation memories."
    )

    constraints: List[str] = [
        "Prioritize the summary of answers to user questions from the improved resource"
        " text. If no relevant information is found, summarize it from the historical"
        " dialogue memory given. It is forbidden to make up your own.",
        "You need to first detect user's question that you need to answer with your "
        "summarization.",
        "Extract the provided text content used for summarization.",
        "Then you need to summarize the extracted text content.",
        "Output the content of summarization ONLY related to user's question. The "
        "output language must be the same to user's question language.",
        "If you think the provided text content is not related to user questions at "
        "all, ONLY output 'Did not find the information you want.'!!.",
    ]
    desc: str = (
        "You can summarize provided text content according to user's questions "
        "and output the summarization."
    )

    def __init__(self, **kwargs):
        """Create a new instance."""
        super().__init__(**kwargs)
        self._init_actions([IndicatorAction])
