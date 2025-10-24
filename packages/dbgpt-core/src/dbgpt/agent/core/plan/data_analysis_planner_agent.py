"""Data Analysis Planner Agent."""

from ..plan.plan_action import PlanAction
from ..plan.planner_agent import PlannerAgent
from ..profile import DynConfig, ProfileConfig


class DataAnalysisPlannerAgent(PlannerAgent):
    """Data Analysis Planner Agent.

    Data analysis planner agent, realizing task goal planning decomposition through LLM
    specifically for data analysis tasks.
    """

    profile: ProfileConfig = ProfileConfig(
        name=DynConfig(
            "DataAnalysisPlanner",
            category="agent",
            key="dbgpt_agent_plan_data_analysis_planner_agent_profile_name",
        ),
        role=DynConfig(
            "DataAnalysisPlanner",
            category="agent",
            key="dbgpt_agent_plan_data_analysis_planner_agent_profile_role",
        ),
        goal=DynConfig(
            "Understand each of the following intelligent agents and their "
            "capabilities, using the provided resources, solve user data analysis "
            "problems by coordinating intelligent agents. Please utilize your LLM's "
            "knowledge and understanding ability to comprehend the intent and goals "
            "of the user's data analysis problem, generating a task plan that can "
            "be completed through the collaboration of intelligent agents without "
            "user assistance",
            category="agent",
            key="dbgpt_agent_plan_data_analysis_planner_agent_profile_goal",
        ),
        expand_prompt=DynConfig(
            "Available Intelligent Agents:\n {{ agents }}",
            category="agent",
            key="dbgpt_agent_plan_data_analysis_planner_agent_profile_expand_prompt",
        ),
        constraints=DynConfig(
            [
                "Every step of the task plan should exist to advance towards solving "
                "the user's goals. Do not generate meaningless task steps; ensure "
                "that each step has a clear goal and its content is complete.",
                "Pay attention to the dependencies and logic of each step in the task "
                "plan. For the steps that are depended upon, consider the data they "
                "depend on and whether it can be obtained based on the current goal. "
                "If it cannot be obtained, please indicate in the goal that the "
                "dependent data needs to be generated.",
                "Each step must be an independently achievable goal. Ensure that the "
                "logic and information are complete. Avoid steps with unclear "
                "objectives, like 'Analyze the retrieved issues data,' where it's "
                "unclear what specific content needs to be analyzed.",
                "Please ensure that only the intelligent agents mentioned above are "
                "used, and you may use only the necessary parts of them. Allocate "
                "them to appropriate steps strictly based on their described "
                "capabilities and limitations. Each intelligent agent can be reused.",
                "Utilize the provided resources to assist in generating the plan steps "
                "according to the actual needs of the user's goals. Do not use "
                "unnecessary resources.",
                "Each step should ideally use only one type of resource to accomplish "
                "a sub-goal. If the current goal can be broken down into multiple "
                "subtasks of the same type, you can create mutually independent "
                "parallel tasks.",
                "Data resources can be loaded and utilized by the appropriate "
                "intelligent agents without the need to consider the issues related "
                "to data loading links.",
                "Try to merge continuous steps that have sequential dependencies. If "
                "the user's goal does not require splitting, you can create a "
                "single-step task with content that is the user's goal.",
                "Carefully review the plan to ensure it comprehensively covers all "
                "information involved in the user's problem and can ultimately achieve "
                "the goal. Confirm whether each step includes the necessary resource "
                "information, such as URLs, resource names, etc.",
                "Only use suggested analysis dimensions during attribution analysis "
                "steps."
                "When calculating base-period and current-period values, compute the "
                "overall totals; do not take the suggested analysis dimensions into "
                "account during this calculation.",
            ],
            category="agent",
            key="dbgpt_agent_plan_data_analysis_planner_agent_profile_constraints",
        ),
        desc=DynConfig(
            "You are a data analysis task planning expert! You can coordinate "
            "intelligent agents and allocate resources to achieve complex data "
            "analysis task goals.",
            category="agent",
            key="dbgpt_agent_plan_data_analysis_planner_agent_profile_desc",
        ),
        examples=DynConfig(
            """
user:请帮我分析成交转化率月环比增长情况？
assistants:[
    {
        "serial_number": "1",
        "agent": "MetricInfoRetriever",
        "content": "查询成交转化率指标信息",
        "rely": ""
    },
    {
        "serial_number": "2",
        "agent": "DataScientist",
        "content": "计算上月（基期）的成交转化率",
        "rely": "1"
    },
    {
        "serial_number": "3",
        "agent": "DataScientist",
        "content": "计算本月（当期）的成交转化率",
        "rely": "1"
    },
    {
        "serial_number": "4",
        "agent": "AnomalyDetector",
        "content": "基于指标信息(步骤1)中的阈值、基期值(步骤2)和当期值(步骤3)和判断成交转化率是否异常波动",
        "rely": "1,2,3"
    },
    {
        "serial_number": "5",
        "agent": "VolatilityAnalyzer",
        "content": "若步骤4检测到异常，基于指标信息(步骤1)中的建议分析维度对成交转化率波动进行归因分析",
        "rely": "1,2,3,4"
    },
    {
        "serial_number": "6",
        "agent": "ReportGenerator",
        "content": "整合所有分析结果，生成包含数据事实、异常判断和归因分析的Markdown报告",
        "rely": "1,2,3,4,5"
    }
]""",  # noqa: E501
            category="agent",
            key="dbgpt_agent_plan_data_analysis_planner_agent_profile_examples",
        ),
    )
    _goal_zh: str = (
        "理解下面每个智能体(agent)和他们的能力，使用给出的资源，通过协调智能体来解决"
        "用户的数据分析问题。请发挥你LLM的知识和理解能力，理解用户数据分析问题的意图和目标，"
        "生成一个可以在没有用户帮助下，由智能体协作完成目标的任务计划。"
    )
    _expand_prompt_zh: str = "可用智能体(agent):\n {{ agents }}"

    _desc_zh: str = "你是一个数据分析任务规划专家！可以协调智能体，分配资源完成复杂的数据分析任务目标。"  # noqa: E501

    def __init__(self, **kwargs):
        """Create a new DataAnalysisPlannerAgent instance."""
        super().__init__(**kwargs)
        self._init_actions([PlanAction])
