"""CommunitySummarizer class."""

import logging

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_summarizer import LLMSummarizer

logger = logging.getLogger(__name__)

COMMUNITY_SUMMARY_EXTRACT_PT = (
    """Task: Summarize Knowledge Graph Community

        You are given a community from a knowledge graph with the following information:
        1. Nodes (entities) with their descriptions
        2. Relationships between nodes with their descriptions

        Goal: Create a concise summary that:
        1. Identifies the main themes or topics of this community
        2. Highlights key entities and their roles
        3. Summarizes the most important relationships
        4. Provides an overall characterization of what this community represents

        Community Data:\n{graph}

        Summary:
    """
)


class CommunitySummarizer(LLMSummarizer):
    """CommunitySummarizer class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the CommunitySummaryExtractor."""
        super().__init__(llm_client, model_name, COMMUNITY_SUMMARY_EXTRACT_PT)
