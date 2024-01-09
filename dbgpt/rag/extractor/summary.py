from typing import List, Optional

from dbgpt._private.llm_metadata import LLMMetadata
from dbgpt.core import LLMClient, ModelRequest, ModelMessageRoleType
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.extractor.base import Extractor
from dbgpt.util import utils
from dbgpt.util.chat_util import run_async_tasks

SUMMARY_PROMPT_TEMPLATE_ZH = """请根据提供的上下文信息的进行精简地总结:
{context}
答案尽量精确和简单,不要过长，长度控制在100字左右
"""

SUMMARY_PROMPT_TEMPLATE_EN = """
Write a quick summary of the following context: 
{context}
the summary should be as concise as possible and not overly lengthy.Please keep the answer within approximately 200 characters.
"""


class SummaryExtractor(Extractor):
    """Summary Extractor, it can extract document summary."""

    def __init__(
        self,
        llm_client: Optional[LLMClient],
        model_name: Optional[str] = None,
        llm_metadata: Optional[LLMMetadata] = None,
        language: Optional[str] = "en",
        max_iteration_with_llm: Optional[int] = 5,
        concurrency_limit_with_llm: Optional[int] = 3,
    ):
        self._llm_client = llm_client
        self._model_name = model_name
        self.llm_metadata = llm_metadata or LLMMetadata
        self._language = language
        self._concurrency_limit_with_llm = concurrency_limit_with_llm
        self._prompt_template = (
            SUMMARY_PROMPT_TEMPLATE_EN
            if language == "en"
            else SUMMARY_PROMPT_TEMPLATE_ZH
        )
        self._concurrency_limit_with_llm = concurrency_limit_with_llm
        self._max_iteration_with_llm = max_iteration_with_llm
        self._concurrency_limit_with_llm = concurrency_limit_with_llm

        """Initialize the Extractor.
        Args:
            llm_client: (Optional[LLMClient]): The LLM client. Defaults to None.
            model_name: str
            llm_metadata: LLMMetadata
            language: (Optional[str]): The language of the prompt. Defaults to "en".
            max_iteration_with_llm: (Optional[int]): The max iteration with llm. Defaults to 5.
            concurrency_limit_with_llm: (Optional[int]): The concurrency limit with llm. Defaults to 3.
        """

    async def _aextract(self, chunks: List[Chunk]) -> str:
        """async document extract summary
        Args:
            - model_name: str
            - chunk_docs: List[Document]
        """
        texts = [doc.content for doc in chunks]
        from dbgpt.util.prompt_util import PromptHelper

        prompt_helper = PromptHelper()
        texts = prompt_helper.repack(
            prompt_template=self._prompt_template, text_chunks=texts
        )
        if len(texts) == 1:
            summary_outs = await self._llm_run_tasks(chunk_texts=texts)
            return summary_outs[0]
        else:
            return await self._mapreduce_extract_summary(docs=texts)

    def _extract(self, chunks: List[Chunk]) -> str:
        """document extract summary
        Args:
            - chunk_docs: List[Document]
        """
        loop = utils.get_or_create_event_loop()
        return loop.run_until_complete(self._aextract(chunks=chunks))

    async def _mapreduce_extract_summary(
        self,
        docs: List[str],
    ) -> str:
        """Extract summary by mapreduce mode
        map -> multi async call llm to generate summary
        reduce -> merge the summaries by map process
        Args:
            docs:List[str]
        Returns:
            summary: str
        """
        if len(docs) == 1:
            return docs[0]
        else:
            summary_outs = await self._llm_run_tasks(
                chunk_texts=docs[0 : self._max_iteration_with_llm]
            )
            from dbgpt.util.prompt_util import PromptHelper

            prompt_helper = PromptHelper()
            summary_outs = prompt_helper.repack(
                prompt_template=self._prompt_template, text_chunks=summary_outs
            )
            return await self._mapreduce_extract_summary(docs=summary_outs)

    async def _llm_run_tasks(self, chunk_texts: List[str]) -> List[str]:
        """llm run tasks
        Args:
            chunk_texts: List[str]
        Returns:
            summary_outs: List[str]
        """
        tasks = []
        for chunk_text in chunk_texts:
            from dbgpt.core import ModelMessage

            prompt = self._prompt_template.format(context=chunk_text)
            messages = [ModelMessage(role=ModelMessageRoleType.SYSTEM, content=prompt)]
            request = ModelRequest(model=self._model_name, messages=messages)
            tasks.append(self._llm_client.generate(request))
        summary_results = await run_async_tasks(
            tasks=tasks, concurrency_limit=self._concurrency_limit_with_llm
        )
        summary_outs = [model_out.text for model_out in summary_results]
        return list(
            filter(
                lambda model_out: "LLMServer Generate Error" not in model_out,
                summary_outs,
            )
        )
