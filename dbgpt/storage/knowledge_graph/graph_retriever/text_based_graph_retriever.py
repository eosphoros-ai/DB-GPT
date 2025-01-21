"""Text Based Graph Retriever."""

import json
import logging
from typing import Dict, List, Tuple, Union

from dbgpt.rag.transformer.simple_intent_translator import SimpleIntentTranslator
from dbgpt.rag.transformer.text2gql import Text2GQL
from dbgpt.storage.graph_store.graph import Graph, MemoryGraph
from dbgpt.storage.knowledge_graph.graph_retriever.base import GraphRetrieverBase

logger = logging.getLogger(__name__)


class TextBasedGraphRetriever(GraphRetrieverBase):
    """Text Based Graph Retriever class."""

    def __init__(self, graph_store_adapter, triplet_topk, llm_client, model_name):
        """Initialize Text Based Graph Retriever."""
        self._graph_store_adapter = graph_store_adapter
        self._triplet_topk = triplet_topk
        self._intent_interpreter = SimpleIntentTranslator(llm_client, model_name)
        self._text2gql = Text2GQL(llm_client, model_name)

    async def retrieve(self, text: str) -> Tuple[Graph, str]:
        """Retrieve from triplets graph with text2gql."""
        intention: Dict[
            str, Union[str, List[str]]
        ] = await self._intent_interpreter.translate(text)
        schema = json.dumps(
            json.loads(self._graph_store_adapter.get_schema()), indent=4
        )
        intention["schema"] = schema
        translation: Dict[str, str] = await self._text2gql.translate(
            json.dumps(intention)
        )
        text2gql_query = translation.get("query", "")
        if "LIMIT" not in text2gql_query:
            text2gql_query += f" LIMIT {self._triplet_topk}"
        try:
            subgraph = self._graph_store_adapter.query(query=text2gql_query)
            logger.info(f"Query executed successfully: {text2gql_query}")
        except Exception as e:
            text2gql_query = ""
            subgraph = MemoryGraph()
            logger.error(f"Failed to execute query: {text2gql_query}\n{e}")

        return subgraph, text2gql_query
