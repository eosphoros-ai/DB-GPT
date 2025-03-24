"""Knowledge graph class."""

import asyncio
import logging
import os
from typing import Any, List, Optional

from dbgpt.core import Chunk, Embeddings, LLMClient
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.rag.transformer.keyword_extractor import KeywordExtractor
from dbgpt.storage.graph_store.base import GraphStoreBase, GraphStoreConfig
from dbgpt.storage.graph_store.graph import Graph
from dbgpt.storage.knowledge_graph.base import KnowledgeGraphBase
from dbgpt.storage.vector_store.filters import MetadataFilters
from dbgpt.util.i18n_utils import _
from dbgpt_ext.rag.transformer.triplet_extractor import TripletExtractor
from dbgpt_ext.storage.graph_store.factory import GraphStoreFactory
from dbgpt_ext.storage.graph_store.tugraph_store import TuGraphStoreConfig
from dbgpt_ext.storage.knowledge_graph.community.base import GraphStoreAdapter
from dbgpt_ext.storage.knowledge_graph.community.factory import GraphStoreAdapterFactory

logger = logging.getLogger(__name__)

GRAPH_PARAMETERS = [
    Parameter.build_from(
        _("Graph Name"),
        "name",
        str,
        description=_("The name of Graph, if not set, will use the default name."),
        optional=True,
        default="dbgpt_collection",
    ),
    Parameter.build_from(
        _("Embedding Function"),
        "embedding_fn",
        Embeddings,
        description=_(
            "The embedding function of vector store, if not set, will use "
            "the default embedding function."
        ),
        optional=True,
        default=None,
    ),
    Parameter.build_from(
        _("Max Chunks Once Load"),
        "max_chunks_once_load",
        int,
        description=_(
            "The max number of chunks to load at once. If your document is "
            "large, you can set this value to a larger number to speed up the loading "
            "process. Default is 10."
        ),
        optional=True,
        default=10,
    ),
    Parameter.build_from(
        _("Max Threads"),
        "max_threads",
        int,
        description=_(
            "The max number of threads to use. Default is 1. If you set "
            "this bigger than 1, please make sure your vector store is thread-safe."
        ),
        optional=True,
        default=1,
    ),
]


# @register_resource(
#     _("Builtin Graph Config"),
#     "knowledge_graph_config",
#     category=ResourceCategory.KNOWLEDGE_GRAPH,
#     description=_("knowledge graph config."),
#     parameters=[
#         *GRAPH_PARAMETERS,
#         Parameter.build_from(
#             _("Knowledge Graph Type"),
#             "graph_store_type",
#             str,
#             description=_("graph store type."),
#             optional=True,
#             default="TuGraph",
#         ),
#         Parameter.build_from(
#             _("LLM Client"),
#             "llm_client",
#             LLMClient,
#             description=_("llm client for extract graph triplets."),
#         ),
#         Parameter.build_from(
#             _("LLM Model Name"),
#             "model_name",
#             str,
#             description=_("llm model name."),
#             optional=True,
#             default=None,
#         ),
#     ],
# )
# @dataclass
# class BuiltinKnowledgeGraphConfig(KnowledgeGraphConfig):
#     """Builtin knowledge graph config."""
#
#     __type__ = "tugraph"
#
#     llm_model: Optional[str] = field(
#         default=None, metadata={"description": "llm model name."}
#     )
#
#     graph_type: Optional[str] = field(
#         default="TuGraph", metadata={"description": "graph store type."}
#     )


@register_resource(
    _("Builtin Knowledge Graph"),
    "builtin_knowledge_graph",
    category=ResourceCategory.KNOWLEDGE_GRAPH,
    description=_("Builtin Knowledge Graph."),
    parameters=[
        Parameter.build_from(
            _("Graph Store Config"),
            "config",
            GraphStoreConfig,
            description=_("graph store config."),
        ),
        Parameter.build_from(
            _("Graph Store Name"),
            "name",
            str,
            optional=True,
            default="dbgpt",
            description=_("Graph Store Name"),
        ),
        Parameter.build_from(
            _("LLM Client"),
            "llm_client",
            LLMClient,
            description=_("llm client for extract graph triplets."),
        ),
        Parameter.build_from(
            _("LLM Model Name"),
            "llm_model",
            str,
            description=_("kg extract llm model name."),
            optional=True,
            default=None,
        ),
    ],
)
class BuiltinKnowledgeGraph(KnowledgeGraphBase):
    """Builtin knowledge graph class."""

    def __init__(
        self,
        config: GraphStoreConfig = None,
        name: Optional[str] = "dbgpt",
        llm_client: Optional[LLMClient] = None,
        llm_model: Optional[str] = None,
    ):
        """Create builtin knowledge graph instance."""
        super().__init__()
        self._config = config
        self._llm_client = llm_client
        self._graph_name = name
        if not self._llm_client:
            raise ValueError("No llm client provided.")

        self._model_name = llm_model
        self._triplet_extractor = TripletExtractor(self._llm_client, self._model_name)
        self._keyword_extractor = KeywordExtractor(self._llm_client, self._model_name)
        self._graph_store: GraphStoreBase = self.__init_graph_store(config)
        self._graph_store_adapter: GraphStoreAdapter = self.__init_graph_store_adapter()

    def __init_graph_store(self, config: GraphStoreConfig) -> GraphStoreBase:
        def configure(cfg: GraphStoreConfig):
            cfg.name = self._graph_name

        graph_store_type = config.get_type_value() or os.getenv("GRAPH_STORE_TYPE")
        return GraphStoreFactory.create(graph_store_type, configure, config.to_dict())

    def __init_graph_store_adapter(self):
        return GraphStoreAdapterFactory.create(self._graph_store)

    def get_config(self) -> TuGraphStoreConfig:
        """Get the knowledge graph config."""
        return self._config

    @property
    def embeddings(self) -> Any:
        """Get the knowledge graph config."""
        return None

    def load_document(self, chunks: List[Chunk]) -> List[str]:
        """Extract and persist triplets to graph store."""

        async def process_chunk(chunk: Chunk):
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                self._graph_store_adapter.insert_triplet(*triplet)
            logger.info(f"load {len(triplets)} triplets from chunk {chunk.chunk_id}")
            return chunk.chunk_id

        # wait async tasks completed
        if not self.vector_name_exists():
            self._graph_store_adapter.create_graph(self._graph_name)
        tasks = [process_chunk(chunk) for chunk in chunks]
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()
        return result

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:  # type: ignore
        """Extract and persist triplets to graph store.

        Args:
            chunks: List[Chunk]: document chunks.
        Return:
            List[str]: chunk ids.
        """
        if not self.vector_name_exists():
            self._graph_store_adapter.create_graph(self._graph_name)
        for chunk in chunks:
            triplets = await self._triplet_extractor.extract(chunk.content)
            for triplet in triplets:
                self._graph_store_adapter.insert_triplet(*triplet)
            logger.info(f"load {len(triplets)} triplets from chunk {chunk.chunk_id}")
        return [chunk.chunk_id for chunk in chunks]

    def similar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search neighbours on knowledge graph."""
        raise Exception("Sync similar_search_with_scores not supported")

    async def asimilar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Search neighbours on knowledge graph."""
        if not filters:
            logger.info("Filters on knowledge graph not supported yet")

        # extract keywords and explore graph store
        keywords = await self._keyword_extractor.extract(text)
        subgraph = self._graph_store_adapter.explore_trigraph(
            keywords, limit=topk
        ).format()

        logger.info(f"Search subgraph from {len(keywords)} keywords")

        if not subgraph:
            return []

        content = (
            "The following entities and relationships provided after "
            "[Subgraph] are retrieved from the knowledge graph "
            "based on the keywords:\n"
            f'"{",".join(keywords)}".\n'
            "---------------------\n"
            "The following examples after [Entities] and [Relationships] that "
            "can help you understand the data format of the knowledge graph, "
            "but do not use them in the answer.\n"
            "[Entities]:\n"
            "(alice)\n"
            "(bob:{age:28})\n"
            '(carry:{age:18;role:"teacher"})\n\n'
            "[Relationships]:\n"
            "(alice)-[reward]->(alice)\n"
            '(alice)-[notify:{method:"email"}]->'
            '(carry:{age:18;role:"teacher"})\n'
            '(bob:{age:28})-[teach:{course:"math";hour:180}]->(alice)\n'
            "---------------------\n"
            f"[Subgraph]:\n{subgraph}\n"
        )
        return [Chunk(content=content)]

    def query_graph(self, limit: Optional[int] = None) -> Graph:
        """Query graph."""
        return self._graph_store_adapter.get_full_graph(limit)

    def truncate(self) -> List[str]:
        """Truncate knowledge graph."""
        logger.info(f"Truncate graph {self._graph_name}")
        self._graph_store_adapter.truncate()

        logger.info("Truncate keyword extractor")
        self._keyword_extractor.truncate()

        logger.info("Truncate triplet extractor")
        self._triplet_extractor.truncate()

        return [self._graph_name]

    def delete_vector_name(self, index_name: str):
        """Delete vector name."""
        logger.info(f"Drop graph {index_name}")
        self._graph_store_adapter.drop()

        logger.info("Drop keyword extractor")
        self._keyword_extractor.drop()

        logger.info("Drop triplet extractor")
        self._triplet_extractor.drop()

    def delete_by_ids(self, ids: str) -> List[str]:
        """Delete by ids."""
        self._graph_store_adapter.delete_document(chunk_id=ids)
        return []

    def vector_name_exists(self) -> bool:
        """Whether name exists."""
        return self._graph_store_adapter.graph_store.is_exist(self._graph_name)
