import logging
from typing import Optional, Tuple

from ..core.agent import AgentMessage
from ..core.base_agent import ConversableAgent
from ..core.profile import DynConfig, ProfileConfig
from ..resource.database import DBResource
from .actions.websearch_action import WebSearchAction

logger = logging.getLogger(__name__)


class WebSearchAgent(ConversableAgent):
    """Web Search Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "WebSearchAdvisor",
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_name",
        ),
        role=DynConfig(
            "WebSearchAgent",
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_role",
        ),
        goal=DynConfig(
            "Comprehensively analyze user questions and existing context "
            "data to determine whether real-time external information is "
            "needed. When necessary, generate accurate search keywords to "
            "obtain the missing information required for a complete answer.",
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Must first conduct a thorough analysis of existing data "
                "and context to identify what information is already "
                "available and what is missing.",
                "Only generate search keywords when existing data is "
                "insufficient to answer the user's question, and the "
                "missing information can only be obtained through "
                "real-time search.",
                "For time-sensitive questions (e.g., holidays, current "
                "events, latest policies), prioritize using web search "
                "to obtain real-time information.",
                "For queries about specific regions, entities, or events, "
                "verify if relevant information exists in the data; if "
                "absent, generate precise search keywords.",
                "Keywords must be specific, unambiguous, and directly "
                "address the identified information gap. Avoid overly "
                "broad or irrelevant terms.",
                "If all necessary information is already present in the "
                "existing data and no external information is needed, "
                "strictly output 'NO_SEARCH_REQUIRED'.",
                "Do not make assumptions about missing data; only generate "
                "searches for information that is explicitly needed to "
                "answer the user's question.",
                "Generated search keywords should be concise and clear, "
                "typically no more than 10 words, ensuring search engines "
                "can return relevant results.",
                "When analyzing data, pay special attention to fields, "
                "values, and relationships relevant to the user's query "
                "topic.",
            ],
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_constraints",
        ),
        desc=DynConfig(
            "Intelligent web search agent specialized in identifying parts "
            "of user questions that require real-time external information. "
            "When user questions involve information missing from existing "
            "data or beyond the model's knowledge (e.g., holiday schedules, "
            "current events, real-time data), automatically triggers web "
            "search to retrieve the latest information.",
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_desc",
        ),
    )

    max_retry_count: int = 3
    language: str = "zh"

    def __init__(self, **kwargs):
        """Create a new Web Search Agent. instance."""
        super().__init__(**kwargs)
        self._init_actions([WebSearchAction])

    @property
    def database(self) -> DBResource:
        return None

    async def correctness_check(
        self, message: AgentMessage
    ) -> Tuple[bool, Optional[str]]:
        """Verify if the current execution results meet expectations."""
        action_out = message.action_report
        if action_out is None:
            return (
                False,
                f"No executable analysis SQL is generated,{message.content}.",
            )

        if not action_out.is_exe_success:
            return (
                False,
                f"Please check your answer, {action_out.content}.",
            )

        if not action_out.content:
            return (
                False,
                "please modify the relevant code of websearch_action",
            )

        return True, None
