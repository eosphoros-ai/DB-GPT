"""Define the CommunitySummaryKnowledgeGraph."""

import logging
import os
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk
from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.rag.transformer.graph_extractor import GraphExtractor
from dbgpt.storage.knowledge_graph.community.community_store import CommunityStore
from dbgpt.storage.knowledge_graph.community.factory import CommunityStoreAdapterFactory
from dbgpt.storage.knowledge_graph.knowledge_graph import (
    BuiltinKnowledgeGraph,
    BuiltinKnowledgeGraphConfig,
)
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.factory import VectorStoreFactory
from dbgpt.storage.vector_store.filters import MetadataFilters

logger = logging.getLogger(__name__)


class CommunitySummaryKnowledgeGraphConfig(BuiltinKnowledgeGraphConfig):
    """Community summary knowledge graph config."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    vector_store_type: str = Field(
        default="Chroma", description="The type of vector store."
    )
    user: Optional[str] = Field(
        default=None,
        description="The user of vector store, if not set, will use the default user.",
    )
    password: Optional[str] = Field(
        default=None,
        description=(
            "The password of vector store, if not set, will use the default password."
        ),
    )
    extract_topk: int = Field(
        default=5,
        description="Topk of knowledge graph extract",
    )
    extract_score_threshold: float = Field(
        default=0.3,
        description="Recall score of knowledge graph extract",
    )
    community_topk: int = Field(
        default=50,
        description="Topk of community search in knowledge graph",
    )
    community_score_threshold: float = Field(
        default=0.0,
        description="Recall score of community search in knowledge graph",
    )


class CommunitySummaryKnowledgeGraph(BuiltinKnowledgeGraph):
    """Community summary knowledge graph class."""

    def __init__(self, config: CommunitySummaryKnowledgeGraphConfig):
        """Initialize community summary knowledge graph class."""
        super().__init__(config)
        self._config = config

        self._vector_store_type = os.getenv(
            "VECTOR_STORE_TYPE", config.vector_store_type
        )
        self._extract_topk = int(
            os.getenv("KNOWLEDGE_GRAPH_EXTRACT_SEARCH_TOP_SIZE", config.extract_topk)
        )
        self._extract_score_threshold = float(
            os.getenv(
                "KNOWLEDGE_GRAPH_EXTRACT_SEARCH_RECALL_SCORE",
                config.extract_score_threshold,
            )
        )
        self._community_topk = int(
            os.getenv(
                "KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_TOP_SIZE", config.community_topk
            )
        )
        self._community_score_threshold = float(
            os.getenv(
                "KNOWLEDGE_GRAPH_COMMUNITY_SEARCH_RECALL_SCORE",
                config.community_score_threshold,
            )
        )

        def extractor_configure(name: str, cfg: VectorStoreConfig):
            cfg.name = name
            cfg.embedding_fn = config.embedding_fn
            cfg.max_chunks_once_load = config.max_chunks_once_load
            cfg.max_threads = config.max_threads
            cfg.user = config.user
            cfg.password = config.password
            cfg.topk = self._extract_topk
            cfg.score_threshold = self._extract_score_threshold

        self._graph_extractor = GraphExtractor(
            self._llm_client,
            self._model_name,
            VectorStoreFactory.create(
                self._vector_store_type,
                config.name + "_CHUNK_HISTORY",
                extractor_configure,
            ),
        )

        def community_store_configure(name: str, cfg: VectorStoreConfig):
            cfg.name = name
            cfg.embedding_fn = config.embedding_fn
            cfg.max_chunks_once_load = config.max_chunks_once_load
            cfg.max_threads = config.max_threads
            cfg.user = config.user
            cfg.password = config.password
            cfg.topk = self._community_topk
            cfg.score_threshold = self._community_score_threshold

        self._community_store = CommunityStore(
            CommunityStoreAdapterFactory.create(self._graph_store),
            CommunitySummarizer(self._llm_client, self._model_name),
            VectorStoreFactory.create(
                self._vector_store_type,
                config.name + "_COMMUNITY_SUMMARY",
                community_store_configure,
            ),
        )

    def get_config(self) -> BuiltinKnowledgeGraphConfig:
        """Get the knowledge graph config."""
        return self._config

    async def aload_document(self, chunks: List[Chunk]) -> List[str]:
        """Extract and persist graph."""
        # todo add doc node
        for chunk in chunks:
            # todo add chunk node
            # todo add relation doc-chunk

            # extract graphs and save
            graphs = await self._graph_extractor.extract(chunk.content)
            for graph in graphs:
                self._graph_store.insert_graph(graph)

        # build communities and save
        await self._community_store.build_communities()

        return [chunk.chunk_id for chunk in chunks]

    async def asimilar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve relevant community summaries."""
        # global search: retrieve relevant community summaries
        communities = await self._community_store.search_communities(text)
        summaries = [
            f"Section {i + 1}:\n{community.summary}"
            for i, community in enumerate(communities)
        ]
        context = "\n".join(summaries) if summaries else ""

        # local search: extract keywords and explore subgraph
        keywords = await self._keyword_extractor.extract(text)
        subgraph = self._graph_store.explore(keywords, limit=topk).format()
        logger.info(f"Search subgraph from {len(keywords)} keywords")

        if not summaries and not subgraph:
            return []

        # merge search results into context
        content = HYBRID_SEARCH_PT_CN.format(context=context, graph=subgraph)
        return [Chunk(content=content)]

    def truncate(self) -> List[str]:
        """Truncate knowledge graph."""
        logger.info("Truncate community store")
        self._community_store.truncate()
        logger.info("Truncate keyword extractor")
        self._keyword_extractor.truncate()
        logger.info("Truncate triplet extractor")
        self._graph_extractor.truncate()
        return [self._config.name]

    def delete_vector_name(self, index_name: str):
        """Delete knowledge graph."""
        logger.info("Drop community store")
        self._community_store.drop()

        logger.info("Drop keyword extractor")
        self._keyword_extractor.drop()

        logger.info("Drop triplet extractor")
        self._graph_extractor.drop()


HYBRID_SEARCH_PT_CN = (
    "## 角色\n"
    "你非常擅长结合提示词模板提供的[上下文]信息与[知识图谱]信息，"
    "准确恰当地回答用户的问题，并保证不会输出与上下文和知识图谱无关的信息。"
    "\n"
    "## 技能\n"
    "### 技能 1: 上下文理解\n"
    "- 准确地理解[上下文]提供的信息，上下文信息可能被拆分为多个章节。\n"
    "- 上下文的每个章节内容都会以[Section]开始，并按需进行了编号。\n"
    "- 上下文信息提供了与用户问题相关度最高的总结性描述，请合理使用它们。"
    "### 技能 2: 知识图谱理解\n"
    "- 准确地识别[知识图谱]中提供的[Entities:]章节中的实体信息"
    "和[Relationships:]章节中的关系信息，实体和关系信息的一般格式为：\n"
    "```"
    "* 实体信息格式:\n"
    "- (实体名)\n"
    "- (实体名:实体描述)\n"
    "- (实体名:实体属性表)\n"
    "- (文本块ID:文档块内容)\n"
    "- (目录ID:目录名)\n"
    "- (文档ID:文档名称)\n"
    "\n"
    "* 关系信息的格式:\n"
    "- (来源实体名)-[关系名]->(目标实体名)\n"
    "- (来源实体名)-[关系名:关系描述]->(目标实体名)\n"
    "- (来源实体名)-[关系名:关系属性表]->(目标实体名)\n"
    "- (文本块实体)-[包含]->(实体名)\n"
    "- (目录ID)-[包含]->(文本块实体)\n"
    "- (目录ID)-[包含]->(子目录ID)\n"
    "- (文档ID)-[包含]->(文本块实体)\n"
    "- (文档ID)-[包含]->(目录ID)\n"
    "```"
    "- 正确地将关系信息中的实体名/ID与实体信息关联，还原出图结构。"
    "- 将图结构所表达的信息作为用户提问的明细上下文，辅助生成更好的答案。\n"
    "\n"
    "## 约束条件\n"
    "- 不要在答案中描述你的思考过程，直接给出用户问题的答案，不要生成无关信息。\n"
    "- 若[知识图谱]没有提供信息，此时应根据[上下文]提供的信息回答问题。"
    "- 确保以第三人称书写，从客观角度结合[上下文]和[知识图谱]表达的信息回答问题。\n"
    "- 若提供的信息相互矛盾，请解决矛盾并提供一个单一、连贯的描述。\n"
    "- 避免使用停用词和过于常见的词汇。\n"
    "\n"
    "## 参考案例\n"
    "```\n"
    "[上下文]:\n"
    "Section 1:\n"
    "菲尔・贾伯的大儿子叫雅各布・贾伯。\n"
    "Section 2:\n"
    "菲尔・贾伯的小儿子叫比尔・贾伯。\n"
    "[知识图谱]:\n"
    "Entities:\n"
    "(菲尔・贾伯#菲尔兹咖啡创始人)\n"
    "(菲尔兹咖啡#加利福尼亚州伯克利创立的咖啡品牌)\n"
    "(雅各布・贾伯#菲尔・贾伯的儿子)\n"
    "(美国多地#菲尔兹咖啡的扩展地区)\n"
    "\n"
    "Relationships:\n"
    "(菲尔・贾伯#创建#菲尔兹咖啡#1978年在加利福尼亚州伯克利创立)\n"
    "(菲尔兹咖啡#位于#加利福尼亚州伯克利#菲尔兹咖啡的创立地点)\n"
    "(菲尔・贾伯#拥有#雅各布・贾伯#菲尔・贾伯的儿子)\n"
    "(雅各布・贾伯#担任#首席执行官#在2005年成为菲尔兹咖啡的首席执行官)\n"
    "(菲尔兹咖啡#扩展至#美国多地#菲尔兹咖啡的扩展范围)\n"
    "```\n"
    "\n"
    "----\n"
    "\n"
    "接下来的[上下文]和[知识图谱]的信息，可以帮助你回答更好地用户的问题。\n"
    "\n"
    "[上下文]:\n"
    "{context}\n"
    "\n"
    "[知识图谱]:\n"
    "{graph}\n"
    "\n"
)

HYBRID_SEARCH_PT_EN = (
    "## Role\n"
    "You excel at combining the information provided in the [Context] with "
    "information from the [KnowledgeGraph] to accurately and appropriately "
    "answer user questions, ensuring that you do not output information "
    "unrelated to the context and knowledge graph.\n"
    "\n"
    "## Skills\n"
    "### Skill 1: Context Understanding\n"
    "- Accurately understand the information provided in the [Context], "
    "which may be divided into several sections.\n"
    "- Each section in the context will start with [Section] "
    "and may be numbered as needed.\n"
    "- The context provides a summary description most relevant to the user’s "
    "question, and it should be used wisely."
    "### Skill 2: Knowledge Graph Understanding\n"
    "- Accurately identify entity information in the [Entities:] section and "
    "relationship information in the [Relationships:] section "
    "of the [KnowledgeGraph]. The general format for entity "
    "and relationship information is:\n"
    "```"
    "* Entity Information Format:\n"
    "- (entity_name)\n"
    "- (entity_name: entity_description)\n"
    "- (entity_name: entity_property_map)\n"
    "- (chunk_id: chunk_content)\n"
    "- (catalog_id: catalog_name)\n"
    "- (document_id: document_name)\n"
    "\n"
    "* Relationship Information Format:\n"
    "- (source_entity_name)-[relationship_name]->(target_entity_name)\n"
    "- (source_entity_name)-[relationship_name: relationship_description]->"
    "(target_entity_name)\n"
    "- (source_entity_name)-[relationship_name: relationship_property_map]->"
    "(target_entity_name)\n"
    "- (chunk_id)-[Contains]->(entity_name)\n"
    "- (catalog_id)-[Contains]->(chunk_id)\n"
    "- (catalog_id)-[Contains]->(sub_catalog_id)\n"
    "- (document_id)-[Contains]->(chunk_id)\n"
    "- (document_id)-[Contains]->(catalog_id)\n"
    "```"
    "- Correctly associate entity names/IDs in the relationship information "
    "with entity information to restore the graph structure."
    "- Use the information expressed by the graph structure as detailed "
    "context for the user's query to assist in generating better answers.\n"
    "\n"
    "## Constraints\n"
    "- Don't describe your thought process in the answer, provide the answer "
    "to the user's question directly without generating irrelevant information."
    "- If the [KnowledgeGraph] does not provide information, you should answer "
    "the question based on the information provided in the [Context]."
    "- Ensure to write in the third person, responding to questions from "
    "an objective perspective based on the information combined from the "
    "[Context] and the [KnowledgeGraph].\n"
    "- If the provided information is contradictory, resolve the "
    "contradictions and provide a single, coherent description.\n"
    "- Avoid using stop words and overly common vocabulary.\n"
    "\n"
    "## Reference Example\n"
    "```\n"
    "[Context]:\n"
    "Section 1:\n"
    "Phil Schiller's eldest son is Jacob Schiller.\n"
    "Section 2:\n"
    "Phil Schiller's youngest son is Bill Schiller.\n"
    "[KnowledgeGraph]:\n"
    "Entities:\n"
    "(Phil Jaber#Founder of Philz Coffee)\n"
    "(Philz Coffee#Coffee brand founded in Berkeley, California)\n"
    "(Jacob Jaber#Son of Phil Jaber)\n"
    "(Multiple locations in the USA#Expansion regions of Philz Coffee)\n"
    "\n"
    "Relationships:\n"
    "(Phil Jaber#Created#Philz Coffee"
    "#Founded in Berkeley, California in 1978)\n"
    "(Philz Coffee#Located in#Berkeley, California"
    "#Founding location of Philz Coffee)\n"
    "(Phil Jaber#Has#Jacob Jaber#Son of Phil Jaber)\n"
    "(Jacob Jaber#Serves as#CEO#Became CEO of Philz Coffee in 2005)\n"
    "(Philz Coffee#Expanded to#Multiple locations in the USA"
    "#Expansion regions of Philz Coffee)\n"
    "```\n"
    "\n"
    "----\n"
    "\n"
    "The following information from the [Context] and [KnowledgeGraph] can "
    "help you better answer user questions.\n"
    "\n"
    "[Context]:\n"
    "{context}\n"
    "\n"
    "[KnowledgeGraph]:\n"
    "{graph}\n"
    "\n"
)
