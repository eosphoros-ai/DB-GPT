"""TripletExtractor class."""
import logging

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.triplet_extractor import TripletExtractor

logger = logging.getLogger(__name__)

SUMMARY_TRIPLET_EXTRACT_PT = (
    # TODO: provide prompt template here
)


class SummaryTripletExtractor(TripletExtractor):
    """SummaryTripletExtractor class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the SummaryTripletExtractor."""
        super().__init__(llm_client, model_name)
        # super()._prompt_template = SUMMARY_TRIPLET_EXTRACT_PT
