import os
from typing import Any, List, Optional

from dbgpt.core import LLMClient
from dbgpt.rag.chunk import Chunk
from dbgpt.rag.chunk_manager import ChunkParameters
from dbgpt.rag.extractor.base import Extractor
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.rag.retriever.base import BaseRetriever
from dbgpt.serve.rag.assembler.base import BaseAssembler


class SummaryAssembler(BaseAssembler):
    """Summary Assembler
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
        knowledge: Knowledge = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        model_name: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        extractor: Optional[Extractor] = None,
        language: Optional[str] = "en",
        **kwargs: Any,
    ) -> None:
        """Initialize with Embedding Assembler arguments.
        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_manager: (Optional[ChunkManager]) ChunkManager to use for chunking.
            model_name: (Optional[str]) llm model to use.
            llm_client: (Optional[LLMClient]) LLMClient to use.
            extractor: (Optional[Extractor]) Extractor to use for summarization.
            language: (Optional[str]) The language of the prompt. Defaults to "en".
        """
        if knowledge is None:
            raise ValueError("knowledge datasource must be provided.")

        self._model_name = model_name or os.getenv("LLM_MODEL")
        self._llm_client = llm_client
        from dbgpt.rag.extractor.summary import SummaryExtractor

        self._extractor = extractor or SummaryExtractor(
            llm_client=self._llm_client, model_name=self._model_name, language=language
        )
        super().__init__(
            knowledge=knowledge,
            chunk_parameters=chunk_parameters,
            extractor=self._extractor,
            **kwargs,
        )

    @classmethod
    def load_from_knowledge(
        cls,
        knowledge: Knowledge = None,
        chunk_parameters: Optional[ChunkParameters] = None,
        model_name: Optional[str] = None,
        llm_client: Optional[LLMClient] = None,
        extractor: Optional[Extractor] = None,
        language: Optional[str] = "en",
        **kwargs: Any,
    ) -> "SummaryAssembler":
        """Load document embedding into vector store from path.
        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameters: (Optional[ChunkParameters]) ChunkManager to use for chunking.
            model_name: (Optional[str]) llm model to use.
            llm_client: (Optional[LLMClient]) LLMClient to use.
            extractor: (Optional[Extractor]) Extractor to use for summarization.
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

    def persist(self) -> List[str]:
        """Persist chunks into store."""

    def _extract_info(self, chunks) -> List[Chunk]:
        """Extract info from chunks."""

    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        """Return a retriever."""
