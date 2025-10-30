"""Knowledge Assistant Agent."""

import logging

from dbgpt.agent import BlankAction, ProfileConfig
from dbgpt.agent.expand.summary_assistant_agent import SummaryAssistantAgent
from dbgpt.rag.retriever.rerank import RetrieverNameRanker
from dbgpt.util.configure import DynConfig

logger = logging.getLogger(__name__)


class KnowledgeAgent(SummaryAssistantAgent):
    """Summary Assistant Agent."""

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "KnowledgeAssistant",
            category="agent",
            key="dbgpt_agent_expand_knowledge_assistant_agent_profile_name",
        ),
        role=DynConfig(
            "KnowledgeAssistant",
            category="agent",
            key="dbgpt_agent_expand_knowledge_assistant_agent_profile_role",
        ),
        goal=DynConfig(
            "基于以下给出的已知信息, 准守规范约束，专业、简要回答用户的问题."
            "根据用户问题找到知识对应的指标，并给出对应的分析SQL",
            category="agent",
            key="dbgpt_agent_expand_knowledge_assistant_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
               """
                1.如果已知信息包含的图片、链接、表格、代码块等特殊markdown标签格式的信息
                 确保在答案中包含原文这些图片、链接、表格和代码标签，不要丢弃不要修改,
                 如:图片格式：![image.png](xxx), 链接格式:[xxx](xxx),
                 表格格式:|xxx|xxx|xxx|, 代码格式:```xxx```.
                 2.如果无法从提供的内容中获取答案, 请说: "知识库中提供的内容不足以回答此问题"
                 禁止胡乱编造.
               """
            ],
            category="agent",
            key="dbgpt_agent_expand_knowledge_assistant_agent_profile_constraints",
        ),
        system_prompt_template=DynConfig(
            "You are a knowledge assistant. You need to 根据用户问题找到知识对应的指标，并给出对应的分析SQL",
            category="agent",
            key="dbgpt_agent_expand_knowledge__assistant_agent_profile_system_prompt_template",
        ),
        desc=DynConfig(
            "You are a knowledge assistant. You need to 根据用户问题找到知识对应的指标，并给出对应的分析SQL",
            category="agent",
            key="dbgpt_agent_expand_knowledge__assistant_agent_profile_desc",
        ),
    )

    def __init__(self, **kwargs):
        """Create a new SummaryAssistantAgent instance."""
        super().__init__(**kwargs)
        self._post_reranks = [RetrieverNameRanker(5)]
        self._init_actions([BlankAction])
