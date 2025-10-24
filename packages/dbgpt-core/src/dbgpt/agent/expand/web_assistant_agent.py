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
            "DataAwareSearchAdvisor",
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_name",
        ),
        role=DynConfig(
            "SearchNeedEvaluator",
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_role",
        ),
        goal=DynConfig(
            "Comprehensively analyze user questions and existing Excel "
            "table data to first determine whether real-time external "
            "information is needed. When necessary, generate accurate "
            "search keywords to obtain the missing information "
            "required for complete answer.",
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Must first conduct a thorough analysis of the Excel "
                "data structure and content to identify what information"
                " is already available and what is missing.",
                "Only generate search keywords when the Excel data is "
                "insufficient to answer the user's question, and the "
                "missing information can only be obtained through real-time search.",
                "For date-related questions, check if the Excel contains "
                "specific date ranges; if not, output search terms for "
                "the required date information (e.g., '2025年国庆节放假安排').",
                "For region-specific queries, verify if location data "
                "exists in the Excel; if absent, generate location-related "
                "search keywords.",
                "Keywords must be specific, unambiguous, and directly "
                "address the identified information gap. Avoid overly "
                "broad or irrelevant terms.",
                "If all necessary information is already present in the "
                "Excel data and no external information is needed, "
                "strictly output 'NO_SEARCH_REQUIRED'.",
                "Do not make assumptions about missing data; only generate "
                "searches for information that is explicitly needed to "
                "answer the user's question.",
                "When analyzing Excel data, pay special attention to columns, "
                "values, and relationships that are relevant to the user's query"
                " topic.",
            ],
            category="agent",
            key="dbgpt_agent_expand_data_aware_search_agent_profile_constraints",
        ),
        desc=DynConfig(
            "If user questions involve data absent from the Excel and"
            " beyond the model’s knowledge (e.g., lunar festivals, "
            "current events, real-time metrics), the Agent must "
            "trigger external search.",
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
        """Verify whether the current execution results meet the target expectations."""
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
