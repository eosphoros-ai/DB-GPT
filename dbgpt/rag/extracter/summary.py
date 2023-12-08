from typing import List

from langchain.schema import Document

from dbgpt._private.llm_metadata import LLMMetadata
from dbgpt.rag.extracter.base import Extractor


class SummaryExtractor(Extractor):
    """Summary Extractor, it can extract document summary."""

    def __init__(self, model_name: str = None, llm_metadata: LLMMetadata = None):
        self.model_name = (model_name,)
        self.llm_metadata = (llm_metadata or LLMMetadata,)

    async def extract(self, chunks: List[Document]) -> str:
        """async document extract summary
        Args:
            - model_name: str
            - chunk_docs: List[Document]
        """
        texts = [doc.page_content for doc in chunks]
        from dbgpt.util.prompt_util import PromptHelper

        prompt_helper = PromptHelper()
        from dbgpt.app.scene.chat_knowledge.summary.prompt import prompt

        texts = prompt_helper.repack(prompt_template=prompt.template, text_chunks=texts)
        return await self._mapreduce_extract_summary(
            docs=texts, model_name=self.model_name, llm_metadata=self.llm_metadata
        )

    async def _mapreduce_extract_summary(
        self,
        docs,
        model_name,
        llm_metadata: LLMMetadata,
    ):
        """Extract summary by mapreduce mode
        map -> multi async call llm to generate summary
        reduce -> merge the summaries by map process
        Args:
            docs:List[str]
            model_name:model name str
            llm_metadata:LLMMetadata
        Returns:
             Document: refine summary context document.
        """
        from dbgpt.app.scene import ChatScene
        from dbgpt._private.chat_util import llm_chat_response_nostream
        import uuid

        tasks = []
        if len(docs) == 1:
            return docs[0]
        else:
            max_iteration = (
                llm_metadata.max_chat_iteration
                if len(docs) > llm_metadata.max_chat_iteration
                else len(docs)
            )
            for doc in docs[0:max_iteration]:
                chat_param = {
                    "chat_session_id": uuid.uuid1(),
                    "current_user_input": "",
                    "select_param": doc,
                    "model_name": model_name,
                    "model_cache_enable": True,
                }
                tasks.append(
                    llm_chat_response_nostream(
                        ChatScene.ExtractSummary.value(), **{"chat_param": chat_param}
                    )
                )
            from dbgpt._private.chat_util import run_async_tasks

            summary_iters = await run_async_tasks(
                tasks=tasks, concurrency_limit=llm_metadata.concurrency_limit
            )
            summary_iters = list(
                filter(
                    lambda content: "LLMServer Generate Error" not in content,
                    summary_iters,
                )
            )
            from dbgpt.util.prompt_util import PromptHelper
            from dbgpt.app.scene.chat_knowledge.summary.prompt import prompt

            prompt_helper = PromptHelper()
            summary_iters = prompt_helper.repack(
                prompt_template=prompt.template, text_chunks=summary_iters
            )
            return await self._mapreduce_extract_summary(
                summary_iters, model_name, max_iteration, llm_metadata.concurrency_limit
            )
