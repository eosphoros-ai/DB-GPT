import logging

from dbgpt.agent import ConversableAgent, get_agent_manager
from dbgpt.agent.core.profile import DynConfig, ProfileConfig
from dbgpt_serve.agent.agents.expand.actions.metric_info_action import (
    MetricInfoAction,
)

logger = logging.getLogger(__name__)


class MetricInfoAgent(ConversableAgent):
    """Metric Info Agent.

    This agent is responsible for retrieving specific metric information by accessing
    knowledge base resources to obtain detailed information about business metrics.
    """

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "MetricInfoRetriever",
            category="agent",
            key="dbgpt_ant_agent_agents_metric_info_agent_profile_name",
        ),
        role=DynConfig(
            "MetricInfoRetriever",
            category="agent",
            key="dbgpt_ant_agent_agents_metric_info_agent_profile_role",
        ),
        goal=DynConfig(
            "Retrieve specific metric information by accessing knowledge base "
            "resources to obtain detailed information about business metrics "
            "including name, field, calculation rules, suggested dimensions, "
            "and thresholds.",
            category="agent",
            key="dbgpt_ant_agent_agents_metric_info_agent_profile_goal",
        ),
        constraints=DynConfig(
            [
                "Only retrieve metric information based on the provided metric name.",
                "Access knowledge base resources to get detailed metric information.",
                "Return structured information including metric name, field, "
                "calculation rules, suggested dimensions, and thresholds.",
            ],
            category="agent",
            key="dbgpt_ant_agent_agents_metric_info_agent_profile_constraints",
        ),
        desc=DynConfig(
            "Retrieve specific metric information from knowledge base resources.",
            category="agent",
            key="dbgpt_ant_agent_agents_metric_info_agent_profile_desc",
        ),
    )
    stream_out: bool = False

    def __init__(self, **kwargs):
        """Create a new MetricInfoAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([MetricInfoAction])


agent_manage = get_agent_manager()
agent_manage.register_agent(MetricInfoAgent)
