import logging
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any, Set, Callable

from langchain.schema import Document

from dbgpt.rag.graph_engine.node import BaseNode, TextNode, NodeWithScore
from dbgpt.rag.graph_engine.search import BaseSearch, SearchMode

logger = logging.getLogger(__name__)
DEFAULT_NODE_SCORE = 1000.0
GLOBAL_EXPLORE_NODE_LIMIT = 3
REL_TEXT_LIMIT = 30


class RAGGraphSearch(BaseSearch):
    """RAG Graph Search.

    args:
        graph_engine RAGGraphEngine.
        model_name (str): model name
            (see :ref:`Prompt-Templates`).
        text_qa_template (Optional[BasePromptTemplate]): A Question Answering Prompt
            (see :ref:`Prompt-Templates`).
        max_keywords_per_query (int): Maximum number of keywords to extract from query.
        num_chunks_per_query (int): Maximum number of text chunks to query.
        search_mode (Optional[SearchMode]): Specifies whether to use keyowrds, default SearchMode.KEYWORD
            embeddings, or both to find relevant triplets. Should be one of "keyword",
            "embedding", or "hybrid".
        graph_store_query_depth (int): The depth of the graph store query.
        extract_subject_entities_fn (Optional[Callback]): extract_subject_entities callback.
    """

    def __init__(
        self,
        graph_engine,
        model_name: str = None,
        max_keywords_per_query: int = 10,
        num_chunks_per_query: int = 10,
        search_mode: Optional[SearchMode] = SearchMode.KEYWORD,
        graph_store_query_depth: int = 2,
        extract_subject_entities_fn: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize params."""
        from dbgpt.rag.graph_engine.graph_engine import RAGGraphEngine

        self.graph_engine: RAGGraphEngine = graph_engine
        self.model_name = model_name or self.graph_engine.model_name
        self._index_struct = self.graph_engine.index_struct
        self.max_keywords_per_query = max_keywords_per_query
        self.num_chunks_per_query = num_chunks_per_query
        self._search_mode = search_mode

        self._graph_store = self.graph_engine.graph_store
        self.graph_store_query_depth = graph_store_query_depth
        self._verbose = kwargs.get("verbose", False)
        refresh_schema = kwargs.get("refresh_schema", False)
        self.extract_subject_entities_fn = extract_subject_entities_fn
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count() * 5)
        try:
            self._graph_schema = self._graph_store.get_schema(refresh=refresh_schema)
        except NotImplementedError:
            self._graph_schema = ""
        except Exception as e:
            logger.warn(f"can not to find graph schema: {e}")
            self._graph_schema = ""

    async def _extract_subject_entities(self, query_str: str) -> Set[str]:
        """extract subject entities."""
        if self.extract_subject_entities_fn is not None:
            return await self.extract_subject_entities_fn(query_str)
        else:
            return await self._extract_entities_by_llm(query_str)

    async def _extract_entities_by_llm(self, text: str) -> Set[str]:
        """extract subject entities from text by llm"""
        from dbgpt.app.scene import ChatScene
        from dbgpt._private.chat_util import llm_chat_response_nostream
        import uuid

        chat_param = {
            "chat_session_id": uuid.uuid1(),
            "current_user_input": text,
            "select_param": "entity",
            "model_name": self.model_name,
        }
        # loop = util.get_or_create_event_loop()
        # entities = loop.run_until_complete(
        #     llm_chat_response_nostream(
        #         ChatScene.ExtractEntity.value(), **{"chat_param": chat_param}
        #     )
        # )
        return await llm_chat_response_nostream(
            ChatScene.ExtractEntity.value(), **{"chat_param": chat_param}
        )

    async def _search(
        self,
        query_str: str,
    ) -> List[Document]:
        """Get nodes for response."""
        node_visited = set()
        keywords = await self._extract_subject_entities(query_str)
        print(f"extract entities: {keywords}\n")
        rel_texts = []
        cur_rel_map = {}
        chunk_indices_count: Dict[str, int] = defaultdict(int)
        if self._search_mode != SearchMode.EMBEDDING:
            for keyword in keywords:
                keyword = keyword.lower()
                subjs = set((keyword,))
                # node_ids = self._index_struct.search_node_by_keyword(keyword)
                # for node_id in node_ids[:GLOBAL_EXPLORE_NODE_LIMIT]:
                #     if node_id in node_visited:
                #         continue
                #
                #     # if self._include_text:
                #     #     chunk_indices_count[node_id] += 1
                #
                #     node_visited.add(node_id)

                rel_map = self._graph_store.get_rel_map(
                    list(subjs), self.graph_store_query_depth
                )
                logger.debug(f"rel_map: {rel_map}")

                if not rel_map:
                    continue
                rel_texts.extend(
                    [
                        str(rel_obj)
                        for rel_objs in rel_map.values()
                        for rel_obj in rel_objs
                    ]
                )
                cur_rel_map.update(rel_map)

        sorted_nodes_with_scores = []
        if not rel_texts:
            logger.info("> No relationships found, returning nodes found by keywords.")
            if len(sorted_nodes_with_scores) == 0:
                logger.info("> No nodes found by keywords, returning empty response.")
            return [Document(page_content="No relationships found.")]

        # add relationships as Node
        # TODO: make initial text customizable
        rel_initial_text = (
            f"The following are knowledge sequence in max depth"
            f" {self.graph_store_query_depth} "
            f"in the form of directed graph like:\n"
            f"`subject -[predicate]->, object, <-[predicate_next_hop]-,"
            f" object_next_hop ...`"
        )
        rel_info = [rel_initial_text] + rel_texts
        rel_node_info = {
            "kg_rel_texts": rel_texts,
            "kg_rel_map": cur_rel_map,
        }
        if self._graph_schema != "":
            rel_node_info["kg_schema"] = {"schema": self._graph_schema}
        rel_info_text = "\n".join(
            [
                str(item)
                for sublist in rel_info
                for item in (sublist if isinstance(sublist, list) else [sublist])
            ]
        )
        if self._verbose:
            print(f"KG context:\n{rel_info_text}\n", color="blue")
        rel_text_node = TextNode(
            text=rel_info_text,
            metadata=rel_node_info,
            excluded_embed_metadata_keys=["kg_rel_map", "kg_rel_texts"],
            excluded_llm_metadata_keys=["kg_rel_map", "kg_rel_texts"],
        )
        # this node is constructed from rel_texts, give high confidence to avoid cutoff
        sorted_nodes_with_scores.append(
            NodeWithScore(node=rel_text_node, score=DEFAULT_NODE_SCORE)
        )
        docs = [
            Document(page_content=node.text, metadata=node.metadata)
            for node in sorted_nodes_with_scores
        ]
        return docs

    def _get_metadata_for_response(
        self, nodes: List[BaseNode]
    ) -> Optional[Dict[str, Any]]:
        """Get metadata for response."""
        for node in nodes:
            if node.metadata is None or "kg_rel_map" not in node.metadata:
                continue
            return node.metadata
        raise ValueError("kg_rel_map must be found in at least one Node.")
