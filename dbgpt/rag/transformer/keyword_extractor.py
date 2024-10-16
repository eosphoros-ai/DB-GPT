"""KeywordExtractor class."""

import logging
from typing import List, Optional

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor

KEYWORD_EXTRACT_PT = (
    "A question is provided below. Given the question, extract up to "
    "keywords from the text. Focus on extracting the keywords that we can use "
    "to best lookup answers to the question.\n"
    "Generate as more as possible synonyms or alias of the keywords "
    "considering possible cases of capitalization, pluralization, "
    "common expressions, etc.\n"
    "Avoid stopwords.\n"
    "Provide the keywords and synonyms in comma-separated format."
    "Formatted keywords and synonyms text should be separated by a semicolon.\n"
    "---------------------\n"
    "Example:\n"
    "Text: Alice is Bob's mother.\n"
    "Keywords:\nAlice,mother,Bob;mummy\n"
    "Text: Philz is a coffee shop founded in Berkeley in 1982.\n"
    "Keywords:\nPhilz,coffee shop,Berkeley,1982;coffee bar,coffee house\n"
    "---------------------\n"
    "Text: {text}\n"
    "Keywords:\n"
)

logger = logging.getLogger(__name__)


class KeywordExtractor(LLMExtractor):
    """KeywordExtractor class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the KeywordExtractor."""
        super().__init__(llm_client, model_name, KEYWORD_EXTRACT_PT)

    def _parse_response(self, text: str, limit: Optional[int] = None) -> List[str]:
        keywords = set()

        lines = text.replace(":", "\n").split("\n")

        for line in lines:
            for part in line.split(";"):
                for s in part.strip().split(","):
                    keyword = s.strip()
                    if keyword:
                        keywords.add(keyword)
                        if limit and len(keywords) >= limit:
                            return list(keywords)

        return list(keywords)
