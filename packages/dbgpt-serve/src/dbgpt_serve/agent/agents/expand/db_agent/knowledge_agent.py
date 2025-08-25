"""Knowledge Assistant Agent."""

import logging

from dbgpt.agent import BlankAction, ProfileConfig
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.rag.retriever.rerank import RetrieverNameRanker
from dbgpt.util.configure import DynConfig

logger = logging.getLogger(__name__)


class KnowledgeAgent(SummaryAssistantAgent):
    """Summary Assistant Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "KnowledgeAssistant",
            category="agent",
            key="dbgpt_agent_expand_summary_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "KnowledgeAssistant",
            category="agent",
            key="dbgpt_agent_expand_summary_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "Summarize answer summaries based on user questions from provided "
            "resource information or from historical conversation memories.",
            category="agent",
            key="dbgpt_agent_expand_summary_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Prioritize the summary of answers to user questions from the improved "
                "resource text. If no relevant information is found, summarize it from "
                "the historical dialogue memory given. It is forbidden to make up your "
                "own.",
                "You need to first detect user's question that you need to answer with "
                "your summarization.",
                "Extract the provided text content used for summarization.",
                "Then you need to summarize the extracted text content.",
                "Output the content of summarization ONLY related to user's question. "
                "The output language must be the same to user's question language.",
                "If you think the provided text content is not related to user "
                "questions at all, ONLY output 'Did not find the information you "
                "want.'!!.",
            ],
            category="agent",
            key="dbgpt_agent_expand_summary_assistant_agent_profile_constraints",
        ),
        system_prompt_template=DynConfig(
            "You are a knowledge assistant. You need to 根据用户问题找到知识对应的指标，并给出对应的分析SQL",
            category="agent",
            key="dbgpt_agent_expand_summary_assistant_agent_profile_system_prompt_template",
        ),
        desc=DynConfig(
            "You are a knowledge assistant. You need to 根据用户问题找到知识对应的指标，并给出对应的分析SQL",
            category="agent",
            key="dbgpt_agent_expand_summary_assistant_agent_profile_desc",
        ),
    )

    def __init__(self, **kwargs):
        """Create a new SummaryAssistantAgent instance."""
        super().__init__(**kwargs)
        self._post_reranks = [RetrieverNameRanker(5)]
        self._init_actions([BlankAction])
