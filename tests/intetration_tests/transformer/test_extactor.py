import json

import pytest

from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
from dbgpt.rag.transformer.keyword_extractor import KeywordExtractor
from dbgpt.rag.transformer.triplet_extractor import TripletExtractor

model_name = "gpt-3.5-turbo"


@pytest.fixture
def llm():
    yield OpenAILLMClient()


@pytest.fixture
def triplet_extractor(llm):
    yield TripletExtractor(llm, model_name)


@pytest.fixture
def keyword_extractor(llm):
    yield KeywordExtractor(llm, model_name)


@pytest.mark.asyncio
async def test_extract_triplet(triplet_extractor):
    triplets = await triplet_extractor.extract(
        "Alice is Bob and Cherry's mother and lives in New York.", 10
    )
    print(json.dumps(triplets))
    assert len(triplets) == 3


@pytest.mark.asyncio
async def test_extract_keyword(keyword_extractor):
    keywords = await keyword_extractor.extract(
        "Alice is Bob and Cherry's mother and lives in New York.",
    )
    print(json.dumps(keywords))
    assert len(keywords) > 0
