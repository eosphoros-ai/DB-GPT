"""Define the CommunitySummaryKnowledgeGraph."""

import logging
import os
import uuid
from typing import List, Optional

from dbgpt._private.pydantic import ConfigDict, Field
from dbgpt.core import Chunk
from dbgpt.rag.transformer.community_summarizer import CommunitySummarizer
from dbgpt.rag.transformer.graph_extractor import GraphExtractor
from dbgpt.storage.graph_store.graph import Edge, GraphElemType, MemoryGraph, Vertex
from dbgpt.storage.knowledge_graph.community.community_store import CommunityStore
from dbgpt.storage.knowledge_graph.community.factory import GraphStoreAdapterFactory
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
        default="Chroma",
        description="The type of vector store.",
    )
    user: Optional[str] = Field(
        default=None,
        description="The user of vector store, if not set, will use the default user.",
    )
    password: Optional[str] = Field(
        default=None,
        description=(
            "The password of vector store, "
            "if not set, will use the default password."
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

        # TODO: refactor to use the knowledge graph config
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
            GraphStoreAdapterFactory.create(self._graph_store),
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
        # Check document
        file_path = chunks[0].metadata["source"] or "Text_Node"
        doc_name = os.path.basename(file_path)
        doc_id = str(uuid.uuid4())

        data_list = self._parse_chunks(chunks)  # parse the chunks by def lod_doc_graph
        graph_of_all = MemoryGraph()

        if (
            os.getenv("ENABLE_DOCUMENT_GRAPH_SEARCH", "").lower() == "false"
            and os.getenv("ENABLE_KNOWLEDGE_GRAPH_SEARCH", "").lower() == "false"
        ):
            raise Exception(
                "ENABLE_DOCUMENT_GRAPH_SEARCH and ENABLE_KNOWLEDGE_GRAPH_SEARCH "
                "can not be both false."
            )

        # Support graph search by the document and the chunks
        if os.getenv("ENABLE_DOCUMENT_GRAPH_SEARCH", "").lower() == "true":
            for chunk_index, chunk in enumerate(data_list):
                # The type of the chunk can not be "document"

                chunk_src = Vertex(
                    vid=chunk["parent_id"],
                    name=chunk["parent_title"],
                    vertex_type=chunk["type"],
                    content=chunk["content"],
                )
                graph_of_all.upsert_vertex(chunk_src)
                chunk_dst = Vertex(
                    vid=chunk["id"],
                    name=chunk["title"],
                    vertex_type=chunk["type"],
                    content=chunk["content"],
                )
                graph_of_all.upsert_vertex(chunk_dst)

                # chunk -> include -> chunk
                chunk_include_chunk = Edge(
                    chunk_src.vid,
                    chunk_dst.vid,
                    name=GraphElemType.INCLUDE.value,
                    edge_type=GraphElemType.CHUNK_INCLUDE_CHUNK.value,
                )
                graph_of_all.append_edge(chunk_include_chunk)

                # chunk -> next -> chunk
                if chunk_index >= 1:
                    chunk_next_chunk = Edge(
                        data_list[chunk_index - 1]["id"],
                        data_list[chunk_index]["id"],
                        name=GraphElemType.NEXT.value,
                        edge_type=GraphElemType.CHUNK_NEXT_CHUNK.value,
                    )
                    graph_of_all.append_edge(chunk_next_chunk)

                # document -> include -> chunk
                if chunk["parent_id"] == "document":
                    chunk_src = Vertex(
                        vid=doc_id,
                        name=doc_name,
                        vertex_type=GraphElemType.DOCUMENT.value,
                        content="",  # the content of the document is empty
                    )
                    graph_of_all.upsert_vertex(chunk_src)
                    doc_include_chunk = Edge(
                        doc_id,
                        chunk_dst.vid,
                        name=GraphElemType.INCLUDE.value,
                        edge_type=GraphElemType.DOCUMENT_INCLUDE_CHUNK.value,
                    )
                    graph_of_all.append_edge(doc_include_chunk)

        # Support knowledge graph search by the entities and the relationships
        if os.getenv("ENABLE_KNOWLEDGE_GRAPH_SEARCH", "").lower() == "true":
            # TODO: Use asyncio to extract graph to accelerate the process
            # (attention to the CAP of the graph db)
            for chunk_index, chunk in enumerate(data_list):
                graphs: List[MemoryGraph] = await self._graph_extractor.extract(
                    chunk["content"]
                )

                for graph in graphs:
                    # Upsert the vertices (entities)
                    for vertex in graph.vertices():
                        graph_of_all.upsert_vertex(vertex)

                        # Connect the chunks to the entities
                        if (
                            os.getenv("ENABLE_DOCUMENT_GRAPH_SEARCH", "").lower()
                            == "true"
                        ):
                            # chunk -> include -> entity
                            chunk_include_entity = Edge(
                                chunk["id"],
                                vertex.vid,
                                name="include",
                                edge_type=GraphElemType.CHUNK_INCLUDE_ENTITY.value,
                            )
                            graph_of_all.append_edge(chunk_include_entity)

                    # Upsert the edges (relationships)
                    for edge in graph.edges():
                        edge.set_prop("_chunk_id", chunk_dst.vid)
                        graph_of_all.append_edge(edge)

        self._graph_store_apdater.upsert_graph(graph_of_all)

        # use asyncio.gather
        # tasks = [self._graph_extractor.extract(chunk.content) for chunk in chunks]
        # results = await asyncio.gather(*tasks)
        # for result in results:
        #     self._graph_store_apdater.upsert_graph(result[0])

        # build communities and save

        await self._community_store.build_communities()

        return [chunk.chunk_id for chunk in chunks]

    def _parse_chunks(slef, chunks: List[Chunk]):
        """Parse the chunks by anlyzing the markdown chunks."""
        # TODO: Need to refact.
        data = []
        for chunk_index, chunk in enumerate(chunks):
            parent = None
            directory_keys = list(chunk.metadata.keys())[:-1]
            parent_level = directory_keys[-2] if len(directory_keys) > 1 else None
            current_level = directory_keys[-1] if directory_keys else "Header0"

            chunk_data = {
                "id": chunk.chunk_id,
                "title": chunk.metadata.get(current_level, "none_header_chunk"),
                "directory_keys": directory_keys,
                "level": current_level,
                "content": chunk.content,
                "parent_id": None,
                "parent_title": None,
                "type": "chunk",
                "chunk_index": chunk_index,
            }

            # Find the parent chunk
            if parent_level:
                for parent_direct in reversed(directory_keys[:-1]):
                    parent_titile = chunk.metadata.get(parent_direct, None)
                    for n in range(chunk_index - 1, -1, -1):
                        metadata = chunks[n].metadata
                        keys = list(metadata.keys())[:-1]
                        if (
                            metadata
                            and parent_direct == keys[-1]
                            and parent_titile == metadata.get(parent_direct)
                        ):
                            parent = chunks[n]
                            chunk_data["parent_id"] = parent.chunk_id
                            chunk_data["parent_title"] = parent_titile
                            break
                        if chunk_index - n > len(directory_keys):
                            break
                    if chunk_data["parent_id"]:
                        break

            if not chunk_data["parent_id"]:
                chunk_data["parent_id"] = "document"
            data.append(chunk_data)
        return data

    async def asimilar_search_with_scores(
        self,
        text,
        topk,
        score_threshold: float,
        filters: Optional[MetadataFilters] = None,
    ) -> List[Chunk]:
        """Retrieve relevant community summaries."""
        # Global search: retrieve relevant community summaries
        communities = await self._community_store.search_communities(text)
        summaries = [
            f"Section {i + 1}:\n{community.summary}"
            for i, community in enumerate(communities)
        ]
        context = "\n".join(summaries) if summaries else ""

        keywords = await self._keyword_extractor.extract(text)

        # Local search: extract keywords and explore subgraph
        subgraph = MemoryGraph()
        subgraph_for_doc = MemoryGraph()

        if os.getenv("ENABLE_KNOWLEDGE_GRAPH_SEARCH", "").lower() == "true":
            subgraph = self._graph_store_apdater.explore(
                subs=keywords, limit=topk, search_method="entity_search"
            )

            if os.getenv("ENABLE_DOCUMENT_GRAPH_SEARCH", "").lower() == "true":
                keywords_for_chunk_search: List[str] = []
                for vertex in subgraph.vertices():
                    keywords_for_chunk_search.append(vertex.name)

                subgraph_for_doc = self._graph_store_apdater.explore(
                    subs=keywords_for_chunk_search,
                    limit=topk,
                    search_method="chunk_search",
                )
        else:
            if os.getenv("ENABLE_DOCUMENT_GRAPH_SEARCH", "").lower() == "true":
                subgraph_for_doc = self._graph_store_apdater.explore(
                    subs=keywords,
                    limit=topk,
                    search_method="chunk_search",
                )

        if len(subgraph.format()) > 2048:
            knowledge_graph_str = subgraph.format()[:2048] + "..."
        else:
            knowledge_graph_str = subgraph.format()
        if len(subgraph_for_doc.format(entities_only=True)) > 4096:
            knowledge_graph_for_doc_str = (
                subgraph_for_doc.format(entities_only=True)[:4096] + "..."
            )
        else:
            knowledge_graph_for_doc_str = subgraph_for_doc.format()

        logger.info(f"Search subgraph from the following keywords:\n{len(keywords)}")

        if not (summaries or knowledge_graph_str or knowledge_graph_for_doc_str):
            return []

        # merge search results into context
        content = HYBRID_SEARCH_PT_CN.format(
            context=context,
            knowledge_graph=knowledge_graph_str,
            knowledge_graph_for_doc=knowledge_graph_for_doc_str,
        )
        logger.info(f"Final GraphRAG queried prompt:\n{content}")
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


HYBRID_SEARCH_PT_CN = """## 角色
你非常擅长结合提示词模板提供的[上下文]信息与[知识图谱]信息，
准确恰当地回答用户的问题，并保证不会输出与上下文和知识图谱无关的信息。

## 技能
### 技能 1: 上下文理解
- 准确地理解[上下文]提供的信息，上下文信息可能被拆分为多个章节。
- 上下文的每个章节内容都会以[Section]开始，并按需进行了编号。
- 上下文信息提供了与用户问题相关度最高的总结性描述，请合理使用它们。
### 技能 2: 知识图谱理解
- 准确地识别[知识图谱]中提供的[Entities:]章节中的实体信息和[Relationships:]章节中的关系信息，实体和关系信息的一般格式为：
```
* 实体信息格式:
- (实体名)
- (实体名:实体描述)
- (实体名:实体属性表)
- (文本块ID:文档块内容)
- (目录ID:目录名)
- (文档ID:文档名称)

* 关系信息的格式:
- (来源实体名)-[关系名]->(目标实体名)
- (来源实体名)-[关系名:关系描述]->(目标实体名)
- (来源实体名)-[关系名:关系属性表]->(目标实体名)
- (文本块实体)-[包含]->(实体名)
- (目录ID)-[包含]->(文本块实体)
- (目录ID)-[包含]->(子目录ID)
- (文档ID)-[包含]->(文本块实体)
- (文档ID)-[包含]->(目录ID)
```
- 正确地将关系信息中的实体名/ID与实体信息关联，还原出图结构。
- 将图结构所表达的信息作为用户提问的明细上下文，辅助生成更好的答案。


## 约束条件
- 不要在答案中描述你的思考过程，直接给出用户问题的答案，不要生成无关信息。
- 若[知识图谱]或者[知识库原文]没有提供信息，此时应根据[上下文]提供的信息回答问题。
- 确保以第三人称书写，从客观角度结合[上下文]、[知识图谱]和[知识库原文]表达的信息回答问题。
- 若提供的信息相互矛盾，请解决矛盾并提供一个单一、连贯的描述。
- 避免使用停用词和过于常见的词汇。

## 参考案例
```
[上下文]:
Section 1:
菲尔・贾伯的大儿子叫雅各布・贾伯。
Section 2:
菲尔・贾伯的小儿子叫比尔・贾伯。

[知识图谱]:
Entities:
(菲尔・贾伯#菲尔兹咖啡创始人)
(菲尔兹咖啡#加利福尼亚州伯克利创立的咖啡品牌)
(雅各布・贾伯#菲尔・贾伯的儿子)
(美国多地#菲尔兹咖啡的扩展地区)

Relationships:
(菲尔・贾伯#创建#菲尔兹咖啡#1978年在加利福尼亚州伯克利创立)
(菲尔兹咖啡#位于#加利福尼亚州伯克利#菲尔兹咖啡的创立地点)
(菲尔・贾伯#拥有#雅各布・贾伯#菲尔・贾伯的儿子)
(雅各布・贾伯#担任#首席执行官#在2005年成为菲尔兹咖啡的首席执行官)
(菲尔兹咖啡#扩展至#美国多地#菲尔兹咖啡的扩展范围)

[知识库原文]:
...
```

----

接下来的[上下文]、[知识图谱]和[知识库原文]的信息，可以帮助你回答更好地用户的问题。

[上下文]:
{context}

[知识图谱]:
{knowledge_graph}

[知识库原文]
{knowledge_graph_for_doc}
"""  # noqa: E501

HYBRID_SEARCH_PT_EN = """## Role
You excel at combining the information provided in the [Context] with
information from the [KnowledgeGraph] to accurately and appropriately
answer user questions, ensuring that you do not output information
unrelated to the context and knowledge graph.

## Skills
### Skill 1: Context Understanding
- Accurately understand the information provided in the [Context],
which may be divided into several sections.
- Each section in the context will start with [Section]
and may be numbered as needed.
- The context provides a summary description most relevant to the user's
question, and it should be used wisely.
### Skill 2: Knowledge Graph Understanding
- Accurately identify entity information in the [Entities:] section and
relationship information in the [Relationships:] section
of the [KnowledgeGraph]. The general format for entity
and relationship information is:
```
* Entity Information Format:
- (entity_name)
- (entity_name: entity_description)
- (entity_name: entity_property_map)
- (chunk_id: chunk_content)
- (catalog_id: catalog_name)
- (document_id: document_name)

* Relationship Information Format:
- (source_entity_name)-[relationship_name]->(target_entity_name)
- (source_entity_name)-[relationship_name: relationship_description]->(target_entity_name)
- (source_entity_name)-[relationship_name: relationship_property_map]->(target_entity_name)
- (chunk_id)-[Contains]->(entity_name)
- (catalog_id)-[Contains]->(chunk_id)
- (catalog_id)-[Contains]->(sub_catalog_id)
- (document_id)-[Contains]->(chunk_id)
- (document_id)-[Contains]->(catalog_id)
```
- Correctly associate entity names/IDs in the relationship information
with entity information to restore the graph structure.
- Use the information expressed by the graph structure as detailed
context for the user's query to assist in generating better answers.

## Constraints
- Don't describe your thought process in the answer, provide the answer
to the user's question directly without generating irrelevant information.
- If the [KnowledgeGraph] or [Knowledge base original text] does not provide information, you should answer
the question based on the information provided in the [Context].
- Ensure to write in the third person, responding to questions from
an objective perspective based on the information combined from the
[Context], the [KnowledgeGraph] and the [Knowledge base original text].
- If the provided information is contradictory, resolve the
contradictions and provide a single, coherent description.
- Avoid using stop words and overly common vocabulary.

## Reference Example
```
[Context]:
Section 1:
Phil Schiller's eldest son is Jacob Schiller.
Section 2:
Phil Schiller's youngest son is Bill Schiller.

[KnowledgeGraph]:
Entities:
(Phil Jaber#Founder of Philz Coffee)
(Philz Coffee#Coffee brand founded in Berkeley, California)
(Jacob Jaber#Son of Phil Jaber)
(Multiple locations in the USA#Expansion regions of Philz Coffee)

Relationships:
(Phil Jaber#Created#Philz Coffee#Founded in Berkeley, California in 1978)
(Philz Coffee#Located in#Berkeley, California#Founding location of Philz Coffee)
(Phil Jaber#Has#Jacob Jaber#Son of Phil Jaber)
(Jacob Jaber#Serves as#CEO#Became CEO of Philz Coffee in 2005)
(Philz Coffee#Expanded to#Multiple locations in the USA#Expansion regions of Philz Coffee)

[Knowledge base original text]
...
```

----

The following information from the [Context], [KnowledgeGraph] and [Knowledge base original text]
can help you better answer user questions.

[Context]:
{context}

[KnowledgeGraph]:
{knowledge_graph}

[Knowledge base original text]
{knowledge_graph_for_doc}
"""  # noqa: E501
