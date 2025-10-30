import logging

from dbgpt.agent import ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt_serve.agent.agents.expand.actions.volatility_analysis_action import (
    VolatilityAnalysisAction,
)

logger = logging.getLogger(__name__)


class VolatilityAnalysisAgent(ConversableAgent):
    """Volatility Analysis Agent.

    This agent performs attribution analysis to identify the root causes of metric
    anomalies by analyzing multi-dimensional data and calculating contribution
    rates of each dimension.
    """

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "VolatilityAnalyzer",
            category="agent",
            key="dbgpt_ant_agent_agents_volatility_analysis_agent_profile_name",
        ),
        role=DynConfig(
            "VolatilityAnalyzer",
            category="agent",
            key="dbgpt_ant_agent_agents_volatility_analysis_agent_profile_role",
        ),
        goal=DynConfig(
            "Perform an analysis on a single dimension by calculating the "
            "contribution rates of its constituent factors to determine "
            "which ones are responsible for the metric anomaly",
            category="agent",
            key="dbgpt_ant_agent_agents_volatility_analysis_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Select a recommended dimension from multiple potential dimensions.",
                "Determine the overall metric value that has already been calculated.",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_volatility_analysis_agent_profile_constraints",
        ),
        desc=DynConfig(
            "用于对存在异常的指标进行归因分析，识别导致波动的根本原因。"
            "该智能体须在 AnomalyDetector 确认异常后调用，并应基于 "
            "MetricInfoRetriever 提供的“建议分析维度”（如“地区”）进行下钻分析。"
            "不得在未检测到异常时主动执行归因。",
            category="agent",
            key="dbgpt_ant_agent_agents_volatility_analysis_agent_profile_desc",
        ),
    )
    stream_out: bool = False

    def __init__(self, **kwargs):
        """Create a new VolatilityAnalysisAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([VolatilityAnalysisAction])


agent_manage = get_agent_manager()
agent_manage.register_agent(VolatilityAnalysisAgent)
