import logging

from dbgpt.agent import ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt_serve.agent.agents.expand.actions.anomaly_detection_action import (
    AnomalyDetectionAction,
)

logger = logging.getLogger(__name__)


class AnomalyDetectionAgent(ConversableAgent):
    """Anomaly Detection Agent.

    This agent is responsible for detecting anomalies in business metrics by comparing
    baseline and current period data, and determining if the metric fluctuations exceed
    predefined thresholds.
    """

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "AnomalyDetector",
            category="agent",
            key="dbgpt_ant_agent_agents_anomaly_detection_agent_profile_name",
        ),
        role=DynConfig(
            "AnomalyDetector",
            category="agent",
            key="dbgpt_ant_agent_agents_anomaly_detection_agent_profile_role",
        ),
        goal=DynConfig(
            "Detect anomalies in business metrics by comparing baseline and "
            "current period data, and determine if the metric fluctuations "
            "exceed predefined thresholds.",
            category="agent",
            key="dbgpt_ant_agent_agents_anomaly_detection_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Only detect anomalies based on the provided baseline and "
                "current period data.",
                "Calculate the fluctuation rate and compare it with the "
                "threshold to determine anomalies.",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_anomaly_detection_agent_profile_constraints",
        ),
        desc=DynConfig(
            "用于判断业务指标是否存在异常波动。该智能体需要接收指标的基期值（如上一周期）、"
            "当期值（如当前周期）以及该指标的波动阈值（通常来自指标元信息），并据此判断是否"
            "发生显著异常。",
            category="agent",
            key="dbgpt_ant_agent_agents_anomaly_detection_agent_profile_desc",
        ),
    )
    stream_out: bool = False

    def __init__(self, **kwargs):
        """Create a new AnomalyDetectionAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([AnomalyDetectionAction])


agent_manage = get_agent_manager()
agent_manage.register_agent(AnomalyDetectionAgent)
