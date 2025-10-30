"""Report Generation Agent for creating analysis reports."""

import logging

from dbgpt.agent import ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt_serve.agent.agents.expand.actions.report_generation_action import (
    ReportGenerationAction,
)

logger = logging.getLogger(__name__)


class ReportGenerationAgent(ConversableAgent):
    """Report Generation Agent.

    This agent integrates all analysis results and generates structured reports in
    Markdown format, providing comprehensive insights on metric fluctuations and
    their root causes.
    """

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "ReportGenerator",
            category="agent",
            key="dbgpt_ant_agent_agents_report_generation_agent_profile_name",
        ),
        role=DynConfig(
            "ReportGenerator",
            category="agent",
            key="dbgpt_ant_agent_agents_report_generation_agent_profile_role",
        ),
        goal=DynConfig(
            "Integrate all analysis results and generate structured reports in "
            "Markdown format, providing comprehensive insights on metric "
            "fluctuations and their root causes.",
            category="agent",
            key="dbgpt_ant_agent_agents_report_generation_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Integrate anomaly detection results and volatility analysis "
                "results (if available).",
                "Generate structured Markdown reports with clear sections and "
                "insights.",
                "Include key metrics, fluctuation analysis, and root cause "
                "identification.",
                "Ensure the report is well-organized and easy to understand for "
                "business users.",
                "The report must be returned in standard Markdown format. However, "
                "any code blocks within the Markdown (e.g., for metric formulas, "
                "SQL snippets, or JSON examples) must not be wrapped with "
                "backticks (```).",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_report_generation_agent_profile_constraints",
        ),
        desc=DynConfig(
            "用于整合所有分析结果（包括原始数据、异常判断、归因结论等），生成结构清晰、"
            "内容完整的 Markdown 格式分析报告。应在所有分析步骤完成后调用，且其输入应"
            "明确依赖前面所有相关步骤的输出。",
            category="agent",
            key="dbgpt_ant_agent_agents_report_generation_agent_profile_desc",
        ),
    )
    stream_out: bool = True

    def __init__(self, **kwargs):
        """Create a new ReportGenerationAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([ReportGenerationAction])

    async def build(self, is_retry_chat: bool = False) -> "ConversableAgent":
        """Build the agent."""
        # Build the parent class first
        agent = await super().build(is_retry_chat)
        # Set higher max_new_tokens for report generation to allow longer reports
        if self.agent_context:
            self.agent_context.max_new_tokens = 4096
        return agent


agent_manage = get_agent_manager()
agent_manage.register_agent(ReportGenerationAgent)
