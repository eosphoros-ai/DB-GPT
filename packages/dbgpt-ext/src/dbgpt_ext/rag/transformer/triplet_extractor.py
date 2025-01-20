"""TripletExtractor class."""

import logging
import re
from typing import Any, List, Optional, Tuple

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor

logger = logging.getLogger(__name__)

TRIPLET_EXTRACT_PT = (
    "Some text is provided below. Given the text, "
    "extract up to knowledge triplets as more as possible "
    "in the form of (subject, predicate, object).\n"
    "Avoid stopwords. The subject, predicate, object can not be none.\n"
    "---------------------\n"
    "Example:\n"
    "Text: Alice is Bob's mother.\n"
    "Triplets:\n(Alice, is mother of, Bob)\n"
    "Text: Alice has 2 apples.\n"
    "Triplets:\n(Alice, has 2, apple)\n"
    "Text: Alice was given 1 apple by Bob.\n"
    "Triplets:(Bob, gives 1 apple, Bob)\n"
    "Text: Alice was pushed by Bob.\n"
    "Triplets:(Bob, pushes, Alice)\n"
    "Text: Bob's mother Alice has 2 apples.\n"
    "Triplets:\n(Alice, is mother of, Bob)\n(Alice, has 2, apple)\n"
    "Text: A Big monkey climbed up the tall fruit tree and picked 3 peaches.\n"
    "Triplets:\n(monkey, climbed up, fruit tree)\n(monkey, picked 3, peach)\n"
    "Text: Alice has 2 apples, she gives 1 to Bob.\n"
    "Triplets:\n"
    "(Alice, has 2, apple)\n(Alice, gives 1 apple, Bob)\n"
    "Text: Philz is a coffee shop founded in Berkeley in 1982.\n"
    "Triplets:\n"
    "(Philz, is, coffee shop)\n(Philz, founded in, Berkeley)\n"
    "(Philz, founded in, 1982)\n"
    "---------------------\n"
    "Text: {text}\n"
    "Triplets:\n"
)


class TripletExtractor(LLMExtractor):
    """TripletExtractor class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the TripletExtractor."""
        super().__init__(llm_client, model_name, TRIPLET_EXTRACT_PT)

    def _parse_response(
        self, text: str, limit: Optional[int] = None
    ) -> List[Tuple[Any, ...]]:
        triplets = []

        for line in text.split("\n"):
            for match in re.findall(r"\((.*?)\)", line):
                splits = match.split(",")
                parts = [split.strip() for split in splits if split.strip()]
                if len(parts) == 3:
                    parts = [
                        p.strip(
                            "`~!@#$%^&*()-=+[]\\{}|;':\",./<>?"
                            "·！￥&*（）—【】、「」；‘’：“”，。、《》？"
                        )
                        for p in parts
                    ]
                    triplets.append(tuple(parts))
                    if limit and len(triplets) >= limit:
                        return triplets

        return triplets
