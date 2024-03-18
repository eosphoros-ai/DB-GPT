import unittest
from unittest.mock import AsyncMock, MagicMock

from dbgpt._private.llm_metadata import LLMMetadata
from dbgpt.core import Chunk
from dbgpt.rag.extractor.summary import SummaryExtractor


class MockLLMClient:
    async def generate(self, request):
        return MagicMock(text=f"Summary for: {request.messages[0].content}")


class TestSummaryExtractor(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.llm_client = MockLLMClient()
        self.llm_client.generate = AsyncMock(side_effect=self.llm_client.generate)

        self.extractor = SummaryExtractor(
            llm_client=self.llm_client,
            model_name="test_model_name",
            llm_metadata=LLMMetadata(),
            language="en",
            max_iteration_with_llm=2,
            concurrency_limit_with_llm=1,
        )

    async def test_single_chunk_extraction(self):
        single_chunk = [Chunk(content="This is a test content.")]
        summary = await self.extractor._aextract(chunks=single_chunk)
        self.assertEqual("This is a test content" in summary, True)

    async def test_multiple_chunks_extraction(self):
        chunks = [Chunk(content=f"Content {i}") for i in range(4)]
        summary = await self.extractor._aextract(chunks=chunks)
        self.assertTrue(summary.startswith("Summary for:"))


if __name__ == "__main__":
    unittest.main()
