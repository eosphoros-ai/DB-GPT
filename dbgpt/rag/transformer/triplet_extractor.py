"""TripletExtractor class."""
import logging
import re
from typing import Any, List, Tuple

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)

TRIPLET_EXTRACT_PT = (
    "Some text is provided below. Given the text, extract up to "
    "knowledge triplets in the form of (subject, predicate, object).\n"
    "Avoid stopwords.\n"
    "---------------------\n"
    "Example:\n"
    "Text: Alice is Bob's mother.\n"
    "Triplets:\n(Alice, is mother of, Bob)\n"
    "Text: Philz is a coffee shop founded in Berkeley in 1982.\n"
    "Triplets:\n"
    "(Philz, is, coffee shop)\n"
    "(Philz, founded in, Berkeley)\n"
    "(Philz, founded in, 1982)\n"
    "---------------------\n"
    "Text: {text}\n"
    "Triplets:\n"
)


class TripletExtractor(LLMExtractor):
    """TripletExtractor class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the TripletExtractor with a LLM client and a specific model."""
        super().__init__(llm_client, model_name, TRIPLET_EXTRACT_PT)

    def _parse_response(self, text: str, limit: int) -> List[Tuple[Any, ...]]:
        triplets = []

        for line in text.split("\n"):
            for match in re.findall(r"\((.*?)\)", line):
                splits = match.split(",")
                parts = [split.strip() for split in splits if split.strip()]
                if len(parts) == 3:
                    triplets.append(tuple(parts))
                    if limit and len(triplets) >= limit:
                        return triplets

        return triplets
