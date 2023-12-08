import logging
from typing import Any, Optional, Callable, Tuple, List

from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from dbgpt.rag.embedding_engine import KnowledgeType
from dbgpt.rag.embedding_engine.knowledge_type import get_knowledge_embedding
from dbgpt.rag.graph_engine.index_struct import KG
from dbgpt.rag.graph_engine.node import TextNode
from dbgpt.util import utils

logger = logging.getLogger(__name__)


class RAGGraphEngine:
    """Knowledge RAG Graph Engine.
    Build a RAG Graph Client can extract triplets and insert into graph store.
    Args:
        knowledge_type (Optional[str]): Default: KnowledgeType.DOCUMENT.value
            extracting triplets.
        knowledge_source (Optional[str]):
        model_name (Optional[str]): llm model name
        graph_store (Optional[GraphStore]): The graph store to use.refrence:llama-index
        include_embeddings (bool): Whether to include embeddings in the index.
            Defaults to False.
        max_object_length (int): The maximum length of the object in a triplet.
            Defaults to 128.
        extract_triplet_fn (Optional[Callable]): The function to use for
            extracting triplets. Defaults to None.
    """

    index_struct_cls = KG

    def __init__(
        self,
        knowledge_type: Optional[str] = KnowledgeType.DOCUMENT.value,
        knowledge_source: Optional[str] = None,
        text_splitter=None,
        graph_store=None,
        index_struct: Optional[KG] = None,
        model_name: Optional[str] = None,
        max_triplets_per_chunk: int = 10,
        include_embeddings: bool = False,
        max_object_length: int = 128,
        extract_triplet_fn: Optional[Callable] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize params."""
        from llama_index.graph_stores import SimpleGraphStore

        # need to set parameters before building index in base class.
        self.knowledge_source = knowledge_source
        self.knowledge_type = knowledge_type
        self.model_name = model_name
        self.text_splitter = text_splitter
        self.index_struct = index_struct
        self.include_embeddings = include_embeddings
        self.graph_store = graph_store or SimpleGraphStore()
        # self.graph_store = graph_store
        self.max_triplets_per_chunk = max_triplets_per_chunk
        self._max_object_length = max_object_length
        self._extract_triplet_fn = extract_triplet_fn

    def knowledge_graph(self, docs=None):
        """knowledge docs into graph store"""
        if not docs:
            if self.text_splitter:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=2000, chunk_overlap=100
                )
            knowledge_source = get_knowledge_embedding(
                knowledge_type=self.knowledge_type,
                knowledge_source=self.knowledge_source,
                text_splitter=self.text_splitter,
            )
            docs = knowledge_source.read()
        if self.index_struct is None:
            self.index_struct = self._build_index_from_docs(docs)

    def _extract_triplets(self, text: str) -> List[Tuple[str, str, str]]:
        """Extract triplets from text by function or llm"""
        if self._extract_triplet_fn is not None:
            return self._extract_triplet_fn(text)
        else:
            return self._llm_extract_triplets(text)

    def _llm_extract_triplets(self, text: str) -> List[Tuple[str, str, str]]:
        """Extract triplets from text by llm"""
        from dbgpt.app.scene import ChatScene
        from dbgpt._private.chat_util import llm_chat_response_nostream
        import uuid

        chat_param = {
            "chat_session_id": uuid.uuid1(),
            "current_user_input": text,
            "select_param": "triplet",
            "model_name": self.model_name,
        }
        loop = utils.get_or_create_event_loop()
        triplets = loop.run_until_complete(
            llm_chat_response_nostream(
                ChatScene.ExtractTriplet.value(), **{"chat_param": chat_param}
            )
        )
        return triplets

    def _build_index_from_docs(self, documents: List[Document]) -> KG:
        """Build the index from nodes.
        Args:documents:List[Document]
        """
        index_struct = self.index_struct_cls()
        triplets = []
        for doc in documents:
            trips = self._extract_triplets_task([doc], index_struct)
            triplets.extend(trips)
        print(triplets)
        text_node = TextNode(text=doc.page_content, metadata=doc.metadata)
        for triplet in triplets:
            subj, _, obj = triplet
            self.graph_store.upsert_triplet(*triplet)
            index_struct.add_node([subj, obj], text_node)
        return index_struct

    def search(self, query):
        from dbgpt.rag.graph_engine.graph_search import RAGGraphSearch

        graph_search = RAGGraphSearch(graph_engine=self)
        return graph_search.search(query)

    def _extract_triplets_task(self, docs, index_struct):
        triple_results = []
        for doc in docs:
            import threading

            thread_id = threading.get_ident()
            print(f"current thread-{thread_id} begin extract triplets task")
            triplets = self._extract_triplets(doc.page_content)
            if len(triplets) == 0:
                triplets = []
            text_node = TextNode(text=doc.page_content, metadata=doc.metadata)
            logger.info(f"extracted knowledge triplets: {triplets}")
            print(
                f"current thread-{thread_id} end extract triplets tasks, triplets-{triplets}"
            )
            triple_results.extend(triplets)
        return triple_results
