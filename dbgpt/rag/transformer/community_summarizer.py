"""CommunitySummarizer class."""

import logging

from dbgpt.core import LLMClient
from dbgpt.rag.transformer.llm_summarizer import LLMSummarizer

logger = logging.getLogger(__name__)

COMMUNITY_SUMMARY_PT_CN = (
    "## 角色\n"
    "你非常擅长知识图谱的信息总结，能根据给定的知识图谱中的实体和关系的名称以及描述"
    "信息，全面、恰当地对知识图谱子图信息做出总结性描述，并且不会丢失关键的信息。\n"
    "\n"
    "## 技能\n"
    "### 技能 1: 实体识别\n"
    "- 准确地识别[Entities:]章节中的实体信息，包括实体名、实体描述信息。\n"
    "- 实体信息的一般格式有:\n"
    "(实体名)\n"
    "(实体名:实体描述)\n"
    "(实体名:实体描述JSON文本)\n"
    "(文档块ID:文档块内容)\n"
    "(章节目录ID:章节目录名)\n"
    "(文档ID:文档名称)\n"
    "\n"
    "### 技能 2: 关系识别\n"
    "- 准确地识别[Relationships:]章节中的关系信息，包括来源实体名、关系名、"
    "目标实体名、关系描述信息。\n"
    "- 关系信息的一般格式有:\n"
    "(来源实体名)-[关系名]->(目标实体名)\n"
    "(来源实体名)-[关系名:关系描述]->(目标实体名)\n"
    "(来源实体名)-[关系名:关系描述JSON文本]->(目标实体名)\n"
    "(文档块实体)-[包含]->(实体名)\n"
    "(章节目录实体)-[包含]->(文档块实体)\n"
    "(章节目录实体)-[包含]->(子章节目录实体)\n"
    "(文档实体)-[包含]->(文档块实体)\n"
    "(文档实体)-[包含]->(章节目录实体)\n"
    "\n"
    "### 技能 3: 图结构理解\n"
    "--请按照如下步骤理解图结构--\n"
    "1. 正确地将关系信息中的来源实体名与实体信息关联。\n"
    "2. 正确地将关系信息中的目标实体名与实体信息关联。\n"
    "3. 根据提供的关系信息还原出图结构。"
    "\n"
    "### 技能 4: 知识图谱总结\n"
    "--请按照如下步骤总结知识图谱--\n"
    "1. 确定知识图谱表达的主题或话题，突出关键实体和关系。"
    "2. 使用准确、恰当的语言总结图结构表达的信息，不要生成与图结构中无关的信息。"
    "\n"
    "## 约束条件\n"
    "- 确保以第三人称书写，从客观角度对知识图谱表达的信息进行总结性描述。\n"
    "- 如果实体或关系的描述信息为空，对最终的总结信息没有贡献，不要生成无关信息。\n"
    "- 如果提供的描述信息相互矛盾，请解决矛盾并提供一个单一、连贯的描述。\n"
    "- 避免使用停用词和过于常见的词汇。\n"
    "\n"
    "## 参考案例\n"
    "输入:\n"
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
    "输出:\n"
    "```\n"
    "菲尔兹咖啡由菲尔・贾伯于1978年在加利福尼亚州伯克利创立。因其独特的混合咖啡而闻名，"
    "菲尔兹已扩展到美国多地。菲尔・贾伯的儿子雅各布・贾伯于2005年成为首席执行官，"
    "并带领公司实现了显著增长。\n"
    "```\n"
    "\n"
    "----\n"
    "\n"
    "请根据接下来[知识图谱]提供的信息，按照上述要求，总结知识图谱表达的信息。\n"
    "\n"
    "[知识图谱]:\n"
    "{graph}\n"
    "\n"
    "[总结]:\n"
    "\n"
)

COMMUNITY_SUMMARY_PT_EN = """Task: Summarize Knowledge Graph Community

        You are given a community from a knowledge graph with the following information:
        1. Nodes (entities) with their descriptions
        2. Relationships between nodes with their descriptions

        Goal: Create a concise summary that:
        1. Identifies the main themes or topics of this community
        2. Highlights key entities and their roles
        3. Summarizes the most important relationships
        4. Provides an overall characterization of what this community represents

        Community Data:\n{graph}

        Summary:
    """


class CommunitySummarizer(LLMSummarizer):
    """CommunitySummarizer class."""

    def __init__(self, llm_client: LLMClient, model_name: str):
        """Initialize the CommunitySummaryExtractor."""
        super().__init__(llm_client, model_name, COMMUNITY_SUMMARY_PT_CN)
