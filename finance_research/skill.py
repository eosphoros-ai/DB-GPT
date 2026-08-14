"""DB-GPT skill integration (lazy import so the package runs standalone too)."""

from typing import Any


def create_finance_skill() -> Any:
    """Return a DB-GPT ``Skill`` for public finance research.

    DB-GPT imports are done lazily so ``finance_research`` remains usable
    outside a DB-GPT installation.
    """
    from dbgpt.agent.skill.base import Skill, SkillMetadata, SkillType

    return Skill(
        metadata=SkillMetadata(
            name="finance_research",
            description=(
                "公开财报采集与可追溯研究分析：搜索公开财报 -> 解析 -> "
                "结构化抽取 -> 来源追踪 -> 分析 -> 引用报告。"
            ),
            version="0.1.0",
            skill_type=SkillType.DataAnalysis,
            tags=["finance", "research", "provenance", "rag"],
        ),
        required_tools=["finance_search", "finance_parse", "finance_extract"],
        config={
            "search_provider": "baidu",
            "max_results": 10,
        },
    )


__all__ = ["create_finance_skill"]
