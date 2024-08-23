"""GraphExtractor class."""

import logging
import re
from typing import List, Optional

from dbgpt.core import Chunk, LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor
from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)

GRAPH_EXTRACT_PT = (
    "Given the HISTORY provided before TEXT (maybe empty), which means relevant information of TEXT, "
    "extract TEXT and summarize knowledge in the following forms:\n"
    "1. Entities: (entity_name, entity_type, entity_description)\n"
    "2. Relationships: (source_entity, target_entity, relationship_description, relationship_strength)\n"
    "3. Keywords: [keyword1, keyword2, ...]\n"
    "4. Entity Summaries: [entity_name, comprehensive_summary]\n"
    "\n"
    "Guidelines:\n"
    "- Extract as many relevant entities, relationships, and keywords as possible.\n"
    "- For entities, use the following types: [Person, Organization, Location, Event, Concept, Product]\n"
    "- For relationships, use a strength score from 1 to 10.\n"
    "- For keywords, include important terms and their synonyms or aliases.\n"
    "- For entity summaries, provide a comprehensive, enriched description that combines all relevant information about the entity.\n"
    "- Consider capitalization, pluralization, and common expressions for keywords.\n"
    "- Avoid stopwords and overly common terms.\n"
    "- Resolve any contradictions and provide coherent summaries.\n"
    "- Write summaries in third person and include entity names for full context.\n"
    "\n"
    "Format:\n"
    "Entities:\n"
    "(entity_name, entity_type, entity_description)\n"
    "...\n"
    "\n"
    "Relationships:\n"
    "(source_entity, target_entity, relationship_description, relationship_strength)\n"
    "...\n"
    "\n"
    "Keywords:\n"
    "[keyword1, synonym1, synonym2]\n"
    "[keyword2, synonym3, synonym4]\n"
    "...\n"
    "\n"
    "Entity Summaries:\n"
    "[entity_name, comprehensive_summary]\n"
    "...\n"
    "\n"
    "---------------------\n"
    "Example:\n"
    "HISTORY: This is a story about Philz Coffee.\n"
    "TEXT: Philz Coffee was founded by Phil Jaber in Berkeley, California in 1978. Known for its unique blends, Philz has expanded to multiple locations across the United States. Phil Jaber's son, Jacob Jaber, became the CEO in 2005 and has led the company through significant growth.\n"
    "\n"
    "Entities:\n"
    "(Philz Coffee, Organization, A coffee shop chain founded in Berkeley)\n"
    "(Phil Jaber, Person, Founder of Philz Coffee)\n"
    "(Berkeley, Location, City in California where Philz Coffee was founded)\n"
    "(Jacob Jaber, Person, CEO of Philz Coffee and son of Phil Jaber)\n"
    "\n"
    "Relationships:\n"
    "(Philz Coffee, Phil Jaber, Phil Jaber founded Philz Coffee, 10)\n"
    "(Philz Coffee, Berkeley, Philz Coffee was founded in Berkeley, 8)\n"
    "(Phil Jaber, Jacob Jaber, Jacob Jaber is Phil Jaber's son, 9)\n"
    "(Jacob Jaber, Philz Coffee, Jacob Jaber is the CEO of Philz Coffee, 10)\n"
    "\n"
    "Keywords:\n"
    "[Philz Coffee, Philz, coffee shop, coffee chain]\n"
    "[Phil Jaber, founder]\n"
    "[Berkeley, California]\n"
    "[unique blends, special coffee mixes]\n"
    "[Jacob Jaber, CEO]\n"
    "\n"
    "Entity Summaries:\n"
    "[Philz Coffee, Philz Coffee is a renowned coffee shop chain founded by Phil Jaber in Berkeley, California in 1978. The company is celebrated for its unique coffee blends and has experienced significant expansion, with multiple locations across the United States. Under the leadership of Jacob Jaber, Phil's son who became CEO in 2005, Philz Coffee has undergone substantial growth and continues to be a prominent player in the specialty coffee industry.]\n"
    "[Phil Jaber, Phil Jaber is the visionary founder of Philz Coffee, establishing the company in Berkeley, California in 1978. His innovative approach to coffee blending and preparation laid the foundation for Philz Coffee's success and unique position in the market. Phil later passed the leadership of the company to his son, Jacob Jaber, fostering a family legacy in the coffee business.]\n"
    "\n"
    "---------------------\n"
    "HISTORY: {history}\n"
    "TEXT: {text}\n"
    "RESULTS:\n"
)


class GraphExtractor(LLMExtractor):
    """GraphExtractor class."""

    def __init__(
        self, llm_client: LLMClient, model_name: str, chunk_history: VectorStoreBase
    ):
        """Initialize the GraphExtractor."""
        super().__init__(llm_client, model_name, GRAPH_EXTRACT_PT)

        self._chunk_history = chunk_history

        config = self._chunk_history.get_config()
        self._vector_space = config.name
        self._max_chunks_once_load = config.max_chunks_once_load
        self._max_threads = config.max_threads
        self._topk = config.topk
        self._score_threshold = config.score_threshold

    async def extract(self, text: str, limit: Optional[int] = None) -> List:
        # load similar chunks
        chunks = await self._chunk_history.asimilar_search_with_scores(
            text, self._topk, self._score_threshold
        )
        history = [chunk.content for chunk in chunks]
        context = "\n".join(history) if history else ""

        try:
            # extract with chunk history
            return await super()._extract(text, context, limit)

        finally:
            # save chunk to history
            await self._chunk_history.aload_document_with_limit(
                [Chunk(content=text, metadata={"relevant_cnt": len(history)})],
                self._max_chunks_once_load,
                self._max_threads,
            )

    def _parse_response(self, text: str, limit: Optional[int] = None) -> List[dict]:
        results = []
        current_section = None

        for line in text.split("\n"):
            line = line.strip()
            if line in [
                "Entities:",
                "Relationships:",
                "Keywords:",
                "Entity Summaries:",
            ]:
                current_section = line[:-1]
            elif line and current_section:
                if current_section == "Entities":
                    match = re.match(r"\((.*?),(.*?),(.*?)\)", line)
                    if match:
                        entity_name, entity_type, entity_description = [
                            part.strip() for part in match.groups()
                        ]
                        results.append(
                            {
                                "type": "entity",
                                "data": {
                                    "name": entity_name,
                                    "type": entity_type,
                                    "description": entity_description,
                                },
                            }
                        )
                elif current_section == "Relationships":
                    match = re.match(r"\((.*?),(.*?),(.*?),(\d+)\)", line)
                    if match:
                        source, target, description, strength = [
                            part.strip() for part in match.groups()
                        ]
                        results.append(
                            {
                                "type": "relationship",
                                "data": {
                                    "source": source,
                                    "target": target,
                                    "description": description,
                                    "strength": int(strength),
                                },
                            }
                        )
                elif current_section == "Keywords":
                    keywords = [k.strip() for k in line.strip("[]").split(",")]
                    results.append({"type": "keywords", "data": keywords})
                elif current_section == "Entity Summaries":
                    match = re.match(r"\[(.*?),(.*?)\]", line)
                    if match:
                        entity_name, summary = [part.strip() for part in match.groups()]
                        results.append(
                            {
                                "type": "entity_summary",
                                "data": {"name": entity_name, "summary": summary},
                            }
                        )

            if limit and len(results) >= limit:
                return results

        return results

    def clean(self):
        self._chunk_history.delete_vector_name(self._vector_space)
