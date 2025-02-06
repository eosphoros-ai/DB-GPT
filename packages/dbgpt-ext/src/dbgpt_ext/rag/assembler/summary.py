"""Summary Assembler."""

import os
from typing import Any, List, Optional

from dbgpt.core import Chunk, LLMClient
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.rag.transformer.base import ExtractorBase

from ..assembler.base import BaseAssembler
from ..chunk_manager import ChunkParameters


class SummaryAssembler(BaseAssembler):
    """Summary Assembler.

    Example:
       .. code-block:: python

           pdf_path = "../../../DB-GPT/docs/docs/awel.md"
           OPEN_AI_KEY = "{your_api_key}"
           OPEN_AI_BASE = "{your_api_base}"
           llm_client = OpenAILLMClient(api_key=OPEN_AI_KEY, api_base=OPEN_AI_BASE)
           knowledge = KnowledgeFactory.from_file_path(pdf_path)
           chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
           assembler = SummaryAssembler.load_from_knowledge(
               knowledge=knowledge,
               chunk_parameters=chunk_parameters,
               llm_client=llm_client,
               model_name="gpt-3.5-turbo",
           )
           summary = await assembler.generate_summary()
    """

    def __init__(
        self,
        knowledge: Knowledge,
        chunk_parameters: Optional[ChunkParameters] = None,
        model_name: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        extractor: Optional[ExtractorBase] = None,
        language: Optional[str] = "en",
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_manager: (Optional[ChunkManager]) ChunkManager to use for chunking.
            model_name: (Optional[str]) llm model to use.
            llm_client: (Optional[LLMClient]) LLMClient to use.
            extractor: (Optional[ExtractorBase]) ExtractorBase to use for summarization.
            language: (Optional[str]) The language of the prompt. Defaults to "en".
        """
        if knowledge is None:
            raise ValueError("knowledge datasource must be provided.")

        model_name = model_name or os.getenv("LLM_MODEL")

        if not extractor:
            from ..transformer.summary import SummaryExtractor

            if not llm_client:
                raise ValueError("llm_client must be provided.")
            if not model_name:
                raise ValueError("model_name must be provided.")
            extractor = SummaryExtractor(
                llm_client=llm_client,
                model_name=model_name,
                language=language,
            )
        if not extractor:
            raise ValueError("extractor must be provided.")

        self._extractor: ExtractorBase = extractor
        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            extractor=self._extractor,
            **kwargs,
        )

    @classmethod
    def load_from_knowledge(
        cls,
        knowledge: Knowledge,
        chunk_parameters: Optional[ChunkParameters] = None,
        model_name: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        extractor: Optional[ExtractorBase] = None,
        language: Optional[str] = "en",
        **kwargs: Any,
    ) -> "SummaryAssembler":
        """Load document embedding into vector store from path.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for
                chunking.
            model_name: (Optional[str]) llm model to use.
            llm_client: (Optional[LLMClient]) LLMClient to use.
            extractor: (Optional[ExtractorBase]) ExtractorBase to use for summarization.
            language: (Optional[str]) The language of the prompt. Defaults to "en".
        Returns:
             SummaryAssembler
        """
        return cls(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            model_name=model_name,
            llm_client=llm_client,
            extractor=extractor,
            language=language,
            **kwargs,
        )

    async def generate_summary(self) -> str:
        """Generate summary."""
        return await self._extractor.aextract(self._chunks)

    def persist(self, **kwargs: Any) -> List[str]:
        """Persist chunks into store."""
        raise NotImplementedError

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""
        return []

    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        """Return a retriever."""
        raise NotImplementedError
