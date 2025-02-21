"""Summary Extractor, it can extract document summary."""

from typing import List, Optional

from dbgpt._private.llm_metadata import LLMMetadata
from dbgpt.core import Chunk, LLMClient, ModelMessageRoleType, ModelRequest
from dbgpt.rag.extractor.base import Extractor
from dbgpt.util import utils
from dbgpt.util.chat_util import run_async_tasks

SUMMARY_PROMPT_TEMPLATE_ZH = """请根据提供的上下文信息的进行精简地总结:
{context}
答案尽量精确和简单,不要过长，长度控制在100字左右, 注意:请用<中文>来进行总结。
"""

SUMMARY_PROMPT_TEMPLATE_EN = """
Write a quick summary of the following context:
{context}
the summary should be as concise as possible and not overly lengthy.Please keep the
answer within approximately 200 characters.
"""

REFINE_SUMMARY_TEMPLATE_ZH = """我们已经提供了一个到某一点的现有总结:{context}
请根据你之前推理的内容进行总结,总结回答的时候最好按照1.2.3.进行. \
注意:请用<中文>来进行总结。
"""

REFINE_SUMMARY_TEMPLATE_EN = """
We have provided an existing summary up to a certain point: {context}, We have the
opportunity to refine the existing summary (only if needed) with some more context
below. \nBased on the previous reasoning, please summarize the final conclusion in
accordance with points 1.2.and 3.
"""


class SummaryExtractor(Extractor):
    """Summary Extractor, it can extract document summary."""

    def __init__(
        self,
        llm_client: LLMClient,
        model_name: str,
        llm_metadata: Optional[LLMMetadata] = None,
        language: Optional[str] = "en",
        max_iteration_with_llm: int = 5,
        concurrency_limit_with_llm: int = 3,
    ):
        """Create SummaryExtractor.

        Args:
            llm_client: (Optional[LLMClient]): The LLM client. Defaults to None.
            model_name: str
            llm_metadata: LLMMetadata
            language: (Optional[str]): The language of the prompt. Defaults to "en".
            max_iteration_with_llm: (Optional[int]): The max iteration with llm.
                Defaults to 5.
            concurrency_limit_with_llm: (Optional[int]): The concurrency limit with llm.
                Defaults to 3.
        """
        self._llm_client = llm_client
        self._model_name = model_name
        self.llm_metadata = llm_metadata
        self._language = language
        self._prompt_template = (
            SUMMARY_PROMPT_TEMPLATE_EN
            if language == "en"
            else SUMMARY_PROMPT_TEMPLATE_ZH
        )
        self._refine_prompt_template = (
            REFINE_SUMMARY_TEMPLATE_EN
            if language == "en"
            else REFINE_SUMMARY_TEMPLATE_ZH
        )
        self._concurrency_limit_with_llm = concurrency_limit_with_llm
        self._max_iteration_with_llm = max_iteration_with_llm

    async def _aextract(self, chunks: List[Chunk]) -> str:
        """Return extracted metadata from chunks of async.

        Args:
            chunks (List[Chunk]): extract metadata from chunks

        Returns:
            str: The summary of the documents.
        """
        texts = [doc.content for doc in chunks]
        from dbgpt.util.prompt_util import PromptHelper

        # repack chunk into prompt to adapt llm model max context window
        prompt_helper = PromptHelper()
        texts = prompt_helper.repack(
            prompt_template=self._prompt_template, text_chunks=texts
        )
        if len(texts) == 1:
            summary_outs = await self._llm_run_tasks(
                chunk_texts=texts, prompt_template=self._refine_prompt_template
            )
            return summary_outs[0]
        else:
            map_reduce_texts = await self._mapreduce_extract_summary(docs=texts)
            summary_outs = await self._llm_run_tasks(
                chunk_texts=[map_reduce_texts],
                prompt_template=self._refine_prompt_template,
            )
            return summary_outs[0]

    def _extract(self, chunks: List[Chunk]) -> str:
        """Return summary of the documents.

        Args:
            chunks(List[Chunk]): list of chunks

        Returns:
            summary: str
        """
        loop = utils.get_or_create_event_loop()
        return loop.run_until_complete(self._aextract(chunks=chunks))

    async def _mapreduce_extract_summary(
        self,
        docs: List[str],
    ) -> str:
        """Return the summary of the documents.

        Extract summary by mapreduce mode.

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
                chunk_texts=docs[0 : self._max_iteration_with_llm],
                prompt_template=self._prompt_template,
            )
            from dbgpt.util.prompt_util import PromptHelper

            prompt_helper = PromptHelper()
            summary_outs = prompt_helper.repack(
                prompt_template=self._prompt_template, text_chunks=summary_outs
            )
            return await self._mapreduce_extract_summary(docs=summary_outs)

    async def _llm_run_tasks(
        self, chunk_texts: List[str], prompt_template: str
    ) -> List[str]:
        """Run llm tasks.

        Args:
            chunk_texts: List[str]
            prompt_template: str

        Returns:
            summary_outs: List[str]
        """
        tasks = []
        for chunk_text in chunk_texts:
            from dbgpt.core import ModelMessage

            prompt = prompt_template.format(context=chunk_text)
            messages = [ModelMessage(role=ModelMessageRoleType.HUMAN, content=prompt)]
            request = ModelRequest(model=self._model_name, messages=messages)
            tasks.append(self._llm_client.generate(request))  # type ignore
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
