"""GraphExtractor class."""

import logging
import re
from typing import List, Optional

from dbgpt.core import Chunk, LLMClient
from dbgpt.rag.transformer.llm_extractor import LLMExtractor
from dbgpt.storage.graph_store.graph import Edge, MemoryGraph, Vertex, Graph
from dbgpt.storage.vector_store.base import VectorStoreBase

logger = logging.getLogger(__name__)

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
    "- 尽可能多的生成文本中提及的实体和关系信息，但不要随意创造不存在的实体和关系。\n"
    "- 确保以第三人称书写，从客观角度描述实体名称、关系名称，以及他们的总结性描述。\n"
    "- 尽可能多地使用关联上下文中的信息丰富实体和关系的内容，这非常重要。\n"
    "- 如果实体或关系的总结描述为空，不提供总结描述信息，不要生成无关的描述信息。\n"
    "- 如果提供的描述信息相互矛盾，请解决矛盾并提供一个单一、连贯的描述。\n"
    "- 实体和关系的名称或者描述文本中如果出现#字符，请使用_字符代替。"
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
    "## 参考案例\n"
    "输入:\n"
    "```\n"
    "[上下文]:\n"
    "菲尔・贾伯的儿子叫雅各布・贾伯。\n"
    "\n"
    "[文本]:\n"
    "菲尔兹咖啡由菲尔・贾伯于1978年在加利福尼亚州伯克利创立。"
    "因其独特的混合咖啡而闻名，\n"
    "菲尔兹已扩展到美国多地。他的儿子于2005年成为首席执行官，"
    "并带领公司实现了显著增长。\n"
    "```\n"
    "\n"
    "输出:\n"
    "```\n"
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

GRAPH_EXTRACT_PT = (

)


class GraphExtractor(LLMExtractor):
    """GraphExtractor class."""

    def __init__(
        self, llm_client: LLMClient, model_name: str,
        chunk_history: VectorStoreBase
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

    def _parse_response(
        self,
        text: str,
        limit: Optional[int] = None
    ) -> List[Graph]:
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
                        name, summary = [
                            part.strip() for part in match.groups()
                        ]
                        graph.upsert_vertex(Vertex(name, description=summary))
                elif current_section == "Relationships":
                    match = re.match(
                        r"\((.*?)#(.*?)#(.*?)#(.*?)\)",
                        line
                    )
                    if match:
                        source, name, target, summary = [
                            part.strip() for part in match.groups()
                        ]
                        edge_count += 1
                        graph.append_edge(Edge(
                            source, target, label=name, description=summary
                        ))

            if limit and edge_count >= limit:
                break

        return [graph]

    def clean(self):
        """Clean chunk history."""
        self._chunk_history.delete_vector_name(self._vector_space)
