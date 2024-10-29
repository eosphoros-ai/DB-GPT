"""GraphExtractor class."""

import asyncio
import logging
import re
from typing import Dict, List, Optional

from dbgpt.core import Chunk, LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor
from dbgpt.storage.graph_store.graph import Edge, Graph, MemoryGraph, Vertex
from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)


class GraphExtractor(LLMExtractor):
    """GraphExtractor class."""

    def __init__(
        self, llm_client: LLMClient, model_name: str, chunk_history: VectorStoreBase
    ):
        """Initialize the GraphExtractor."""
        super().__init__(llm_client, model_name, GRAPH_EXTRACT_PT_CN)
        self._chunk_history = chunk_history

        config = self._chunk_history.get_config()

        self._vector_space = config.name
        self._max_chunks_once_load = config.max_chunks_once_load
        self._max_threads = config.max_threads
        self._topk = config.topk
        self._score_threshold = config.score_threshold

    async def aload_chunk_context(self, texts: List[str]) -> Dict[str, str]:
        """Load chunk context."""
        text_context_map: Dict[str, str] = {}

        for text in texts:
            # Load similar chunks
            chunks = await self._chunk_history.asimilar_search_with_scores(
                text, self._topk, self._score_threshold
            )
            history = [
                f"Section {i + 1}:\n{chunk.content}" for i, chunk in enumerate(chunks)
            ]

            # Save chunk to history
            await self._chunk_history.aload_document_with_limit(
                [Chunk(content=text, metadata={"relevant_cnt": len(history)})],
                self._max_chunks_once_load,
                self._max_threads,
            )

            # Save chunk context to map
            context = "\n".join(history) if history else ""
            text_context_map[text] = context
        return text_context_map

    async def extract(self, text: str, limit: Optional[int] = None) -> List:
        """Extract graphs from text.

        Suggestion: to extract triplets in batches, call `batch_extract`.
        """
        # Load similar chunks
        text_context_map = await self.aload_chunk_context([text])
        context = text_context_map[text]

        # Extract with chunk history
        return await super()._extract(text, context, limit)

    async def batch_extract(
        self,
        texts: List[str],
        batch_size: int = 1,
        limit: Optional[int] = None,
    ) -> List[List[Graph]]:
        """Extract graphs from chunks in batches.

        Returns list of graphs in same order as input texts (text <-> graphs).
        """
        if batch_size < 1:
            raise ValueError("batch_size >= 1")

        # 1. Load chunk context
        text_context_map = await self.aload_chunk_context(texts)

        # Pre-allocate results list to maintain order
        graphs_list: List[List[Graph]] = [None] * len(texts)
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min((batch_idx + 1) * batch_size, len(texts))
            batch_texts = texts[start_idx:end_idx]

            # 2. Create tasks with their original indices
            extraction_tasks = [
                (
                    idx,
                    self._extract(text, text_context_map[text], limit),
                )
                for idx, text in enumerate(batch_texts, start=start_idx)
            ]

            # 3. Process extraction in parallel while keeping track of indices
            batch_results = await asyncio.gather(
                *(task for _, task in extraction_tasks)
            )

            # 4. Place results in the correct positions
            for (idx, _), graphs in zip(extraction_tasks, batch_results):
                graphs_list[idx] = graphs

        assert all(x is not None for x in graphs_list), "All positions should be filled"
        return graphs_list

    def _parse_response(self, text: str, limit: Optional[int] = None) -> List[Graph]:
        graph = MemoryGraph()
        edge_count = 0
        current_section = None
        for line in text.split("\n"):
            line = line.strip()
            if line in ["Entities:", "Relationships:"]:
                current_section = line[:-1]
            elif line and current_section:
                if current_section == "Entities":
                    match = re.match(r"\((.*?)#(.*?)\)", line)
                    if match:
                        name, summary = [part.strip() for part in match.groups()]
                        graph.upsert_vertex(
                            Vertex(name, description=summary, vertex_type="entity")
                        )
                elif current_section == "Relationships":
                    match = re.match(r"\((.*?)#(.*?)#(.*?)#(.*?)\)", line)
                    if match:
                        source, name, target, summary = [
                            part.strip() for part in match.groups()
                        ]
                        edge_count += 1
                        graph.append_edge(
                            Edge(
                                source,
                                target,
                                name,
                                description=summary,
                                edge_type="relation",
                            )
                        )

            if limit and edge_count >= limit:
                break

        return [graph]

    def truncate(self):
        """Truncate chunk history."""
        self._chunk_history.truncate()

    def drop(self):
        """Drop chunk history."""
        self._chunk_history.delete_vector_name(self._vector_space)


GRAPH_EXTRACT_PT_CN = (
    "## 角色\n"
    "你是一个知识图谱工程专家，非常擅长从文本中精确抽取知识图谱的实体"
    "（主体、客体）和关系，并能对实体和关系的含义做出恰当的总结性描述。\n"
    "\n"
    "## 技能\n"
    "### 技能 1: 实体抽取\n"
    "--请按照如下步骤抽取实体--\n"
    "1. 准确地识别文本中的实体信息，一般是名词、代词等。\n"
    "2. 准确地识别实体的修饰性描述，一般作为定语对实体特征做补充。\n"
    "3. 对相同概念的实体（同义词、别称、代指），请合并为单一简洁的实体名，"
    "并合并它们的描述信息。\n"
    "4. 对合并后的实体描述信息做简洁、恰当、连贯的总结。\n"
    "\n"
    "### 技能 2: 关系抽取\n"
    "--请按照如下步骤抽取关系--\n"
    "1. 准确地识别文本中实体之间的关联信息，一般是动词、代词等。\n"
    "2. 准确地识别关系的修饰性描述，一般作为状语对关系特征做补充。\n"
    "3. 对相同概念的关系（同义词、别称、代指），请合并为单一简洁的关系名，"
    "并合并它们的描述信息。\n"
    "4. 对合并后的关系描述信息做简洁、恰当、连贯的总结。\n"
    "\n"
    "### 技能 3: 关联上下文\n"
    "- 关联上下文来自与当前待抽取文本相关的前置段落内容，"
    "可以为知识抽取提供信息补充。\n"
    "- 合理利用提供的上下文信息，知识抽取过程中出现的内容引用可能来自关联上下文。\n"
    "- 不要对关联上下文的内容做知识抽取，而仅作为关联信息参考。\n"
    "- 关联上下文是可选信息，可能为空。\n"
    "\n"
    "## 约束条件\n"
    "- 如果文本已提供了图结构格式的数据，直接转换为输出格式返回，"
    "不要修改实体或ID名称。"
    "- 尽可能多的生成文本中提及的实体和关系信息，但不要随意创造不存在的实体和关系。\n"
    "- 确保以第三人称书写，从客观角度描述实体名称、关系名称，以及他们的总结性描述。\n"
    "- 尽可能多地使用关联上下文中的信息丰富实体和关系的内容，这非常重要。\n"
    "- 如果实体或关系的总结描述为空，不提供总结描述信息，不要生成无关的描述信息。\n"
    "- 如果提供的描述信息相互矛盾，请解决矛盾并提供一个单一、连贯的描述。\n"
    "- 实体和关系的名称或者描述文本出现#和:字符时，使用_字符替换，其他字符不要修改。"
    "- 避免使用停用词和过于常见的词汇。\n"
    "\n"
    "## 输出格式\n"
    "Entities:\n"
    "(实体名#实体总结)\n"
    "...\n\n"
    "Relationships:\n"
    "(来源实体名#关系名#目标实体名#关系总结)\n"
    "...\n"
    "\n"
    "## 参考案例"
    "--案例仅帮助你理解提示词的输入和输出格式，请不要在答案中使用它们。--\n"
    "输入:\n"
    "```\n"
    "[上下文]:\n"
    "Section 1:\n"
    "菲尔・贾伯的大儿子叫雅各布・贾伯。\n"
    "Section 2:\n"
    "菲尔・贾伯的小儿子叫比尔・贾伯。\n"
    "..."
    "\n"
    "[文本]:\n"
    "菲尔兹咖啡由菲尔・贾伯于1978年在加利福尼亚州伯克利创立。"
    "因其独特的混合咖啡而闻名，菲尔兹已扩展到美国多地。"
    "他的大儿子于2005年成为首席执行官，并带领公司实现了显著增长。\n"
    "```\n"
    "\n"
    "输出:\n"
    "```\n"
    "Entities:\n"
    "(菲尔・贾伯#菲尔兹咖啡创始人)\n"
    "(菲尔兹咖啡#加利福尼亚州伯克利创立的咖啡品牌)\n"
    "(雅各布・贾伯#菲尔・贾伯的大儿子)\n"
    "(美国多地#菲尔兹咖啡的扩展地区)\n"
    "\n"
    "Relationships:\n"
    "(菲尔・贾伯#创建#菲尔兹咖啡#1978年在加利福尼亚州伯克利创立)\n"
    "(菲尔兹咖啡#位于#加利福尼亚州伯克利#菲尔兹咖啡的创立地点)\n"
    "(菲尔・贾伯#拥有#雅各布・贾伯#菲尔・贾伯的大儿子)\n"
    "(雅各布・贾伯#管理#菲尔兹咖啡#在2005年担任首席执行官)\n"
    "(菲尔兹咖啡#扩展至#美国多地#菲尔兹咖啡的扩展范围)\n"
    "```\n"
    "\n"
    "----\n"
    "\n"
    "请根据接下来[上下文]提供的信息，按照上述要求，抽取[文本]中的实体和关系数据。\n"
    "\n"
    "[上下文]:\n"
    "{history}\n"
    "\n"
    "[文本]:\n"
    "{text}\n"
    "\n"
    "[结果]:\n"
    "\n"
)

GRAPH_EXTRACT_PT_EN = (
    "## Role\n"
    "You are an expert in Knowledge Graph Engineering, skilled at extracting "
    "entities (subjects, objects) and relations from text, and summarizing "
    "their meanings effectively.\n"
    "\n"
    "## Skills\n"
    "### Skill 1: Entity Extraction\n"
    "--Please follow these steps to extract entities--\n"
    "1. Accurately identify entity information in the text, "
    "usually nouns, pronouns, etc.\n"
    "2. Accurately identify descriptive information, "
    "usually as adjectives, that supplements entity features.\n"
    "3. Merge synonymous, alias, or reference entities into "
    "a single concise entity name, and merge their descriptive information.\n"
    "4. Provide a concise, appropriate, and coherent summary "
    "of the combined entity descriptions.\n"
    "\n"
    "### Skill 2: Relation Extraction\n"
    "--Please follow these steps to extract relations--\n"
    "1. Accurately identify relation information between entities in the text, "
    "usually verbs, pronouns, etc.\n"
    "2. Accurately identify descriptive information, usually as adverbs, "
    "that supplements relation features.\n"
    "3. Merge synonymous, alias, or reference relations into "
    "a single concise relation name, and merge their descriptive information.\n"
    "4. Provide a concise, appropriate, and coherent summary "
    "of the combined relation descriptions.\n"
    "\n"
    "### Skill 3: Contextual Association\n"
    "- Context comes from preceding paragraphs related to the current "
    "extraction text and can provide supplementary information.\n"
    "- Appropriately use contextual information, content references "
    "during extraction may come from this context.\n"
    "- Do not extract knowledge from contextual content, "
    "use it only as a reference.\n"
    "- Context is optional and may be empty.\n"
    "\n"
    "## Constraints\n"
    "- If the text has provided data that is similar to or the same as the "
    "output format, please format the output directly according to the "
    "output format requirements."
    "- Generate as much entity and relation information mentioned in the text "
    "as possible, but do not create nonexistent entities or relations.\n"
    "- Ensure the writing is in the third person, describing entity names, "
    "relation names, and their summaries objectively.\n"
    "- Use as much contextual information as possible to enrich the content "
    "of entities and relations, this is very important.\n"
    "- If a summary of an entity or relation is empty, do not provide "
    "summary information, and do not generate irrelevant descriptions.\n"
    "- If provided descriptions are contradictory, resolve the conflict "
    "and provide a single, coherent description.\n"
    "- Replace any # or : characters in entity's and relation's "
    "names or descriptions with an _ character.\n"
    "- Avoid using stop words and overly common terms.\n"
    "\n"
    "## Output Format\n"
    "Entities:\n"
    "(entity_name#entity_summary)\n"
    "...\n\n"
    "Relationships:\n"
    "(source_entity_name#relation_name#target_entity_name#relation_summary)\n"
    "...\n"
    "\n"
    "## Reference Example\n"
    "--The case is only to help you understand the input and output format of "
    "the prompt, please do not use it in your answer.--\n"
    "Input:\n"
    "```\n"
    "[Context]:\n"
    "Section 1:\n"
    "Phil Jabber's eldest son is named Jacob Jabber.\n"
    "Section 2:\n"
    "Phil Jabber's youngest son is named Bill Jabber.\n"
    "..."
    "\n"
    "[Text]:\n"
    "Philz Coffee was founded by Phil Jabber in 1978 in Berkeley, California. "
    "Known for its distinctive blend coffee, Philz has expanded to multiple "
    "locations in the USA. His eldest son became CEO in 2005, "
    "leading significant growth for the company.\n"
    "```\n"
    "\n"
    "Output:\n"
    "```\n"
    "Entities:\n"
    "(Phil Jabber#Founder of Philz Coffee)\n"
    "(Philz Coffee#Coffee brand founded in Berkeley, California)\n"
    "(Jacob Jabber#Phil Jabber's eldest son)\n"
    "(Multiple locations in the USA#Philz Coffee's expansion area)\n"
    "\n"
    "Relationships:\n"
    "(Phil Jabber#Founded#Philz Coffee"
    "#Founded in 1978 in Berkeley, California)\n"
    "(Philz Coffee#Located in#Berkeley, California"
    "#Philz Coffee's founding location)\n"
    "(Phil Jabber#Has#Jacob Jabber#Phil Jabber's eldest son)\n"
    "(Jacob Jabber#Manage#Philz Coffee#Serve as CEO in 2005)\n"
    "(Philz Coffee#Expanded to#Multiple locations in the USA"
    "#Philz Coffee's expansion area)\n"
    "```\n"
    "\n"
    "----\n"
    "\n"
    "Please extract the entities and relationships data from the [Text] "
    "according to the above requirements, using the provided [Context].\n"
    "\n"
    "[Context]:\n"
    "{history}\n"
    "\n"
    "[Text]:\n"
    "{text}\n"
    "\n"
    "[Results]:\n"
    "\n"
)
