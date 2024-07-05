"""KeywordExtractor class."""
import logging
from typing import Optional

from openai._compat import parse_obj
from pydantic import BaseModel, Field

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor
from dbgpt.util.json_utils import find_json_objects

FIN_INTENT_EXTRACT_PROMPT_TEMPLATE = """你是一个金融领域专家，你需要根据用户问题，提取问题中存在的公司名称，年份，以及意图信息\n"
    "以下是一个问题示例：
    "联瑞新材在2020年的综合收益总额是多少元?"
    请您将这些信息提取出来，并以JSON格式的结构回复我，确保您只包含公司名称(company)、年份(year)和我提出的查询意图(intent)。
    你的回复应该像这样：
        "company": "联瑞新材",
        "year": "2020年",
        "intent": "综合收益总额"
    注意：请你回答时使用严格的<JSON>结构返回相应信息。
    "---------------------\n"
    "text: {text}\n"""

logger = logging.getLogger(__name__)


class FinReportIntent(BaseModel):
    """SQL input model."""

    company: str = Field(
        None,
        description="company",
    )
    year: Optional[str] = Field(None, description="year")
    intent: str = Field(None, description="intent")


class FinIntentExtractor(LLMExtractor):
    """KeywordExtractor class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the KeywordExtractor."""
        super().__init__(llm_client, model_name, FIN_INTENT_EXTRACT_PROMPT_TEMPLATE)

    def _parse_response(
        self, text: str, limit: Optional[int] = None
    ) -> FinReportIntent:
        json_objects = find_json_objects(text)
        json_count = len(json_objects)
        if json_count != 1:
            raise ValueError("Unable to obtain valid output.")
        json_result = json_objects[0]
        return parse_obj(FinReportIntent, json_result)
