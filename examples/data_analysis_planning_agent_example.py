"""
Data Analysis Planning Agent Example

This example demonstrates how to use the DataAnalysisPlanningAgent
which can autonomously plan and execute data analysis tasks.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List

import pandas as pd

from dbgpt.agent import ActionOutput, AgentMessage
from dbgpt.agent.expand.data_agent import DataAnalysisPlanningAgent
from dbgpt.agent.resource import ResourcePack, ToolPack
from dbgpt.agent.resource.tool.base import BaseTool, ToolParameter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataSourceTool(BaseTool):
    """Tool for examining data sources."""

    @property
    def name(self) -> str:
        return "examine_data_sources"

    @property
    def description(self) -> str:
        return "Examine available data sources and their structure"

    @property
    def args(self) -> Dict[str, ToolParameter]:
        return {
            "source_type": ToolParameter(
                type="string",
                name="source_type",
                description="Type of data source to examine (file, database, api)",
                required=False,
                default="file",
            )
        }

    async def async_execute(self, **kwargs) -> Dict[str, Any]:
        """Examine available data sources."""
        source_type = kwargs.get("source_type", "file")

        # Simulate examining data sources
        available_sources = {
            "file": [
                {
                    "name": "sales_data.csv",
                    "type": "csv",
                    "size": "2.5MB",
                    "columns": ["date", "product", "sales", "region"],
                },
                {
                    "name": "customer_data.xlsx",
                    "type": "excel",
                    "size": "1.8MB",
                    "columns": ["customer_id", "name", "email", "segment"],
                },
            ],
            "database": [
                {
                    "name": "transactions",
                    "type": "postgresql",
                    "tables": ["sales", "customers", "products"],
                },
                {
                    "name": "analytics",
                    "type": "mysql",
                    "tables": ["events", "users", "sessions"],
                },
            ],
        }

        return {
            "success": True,
            "sources": available_sources.get(source_type, []),
            "message": f"Found {len(available_sources.get(source_type, []))} data sources of type {source_type}",
        }


class LoadDataTool(BaseTool):
    """Tool for loading data."""

    @property
    def name(self) -> str:
        return "load_data"

    @property
    def description(self) -> str:
        return "Load data from specified sources for analysis"

    @property
    def args(self) -> Dict[str, ToolParameter]:
        return {
            "source": ToolParameter(
                type="string",
                name="source",
                description="Data source name or path",
                required=True,
            ),
            "analysis_type": ToolParameter(
                type="string",
                name="analysis_type",
                description="Type of analysis to prepare for (exploratory, statistical, visualization)",
                required=False,
                default="exploratory",
            ),
        }

    async def async_execute(self, **kwargs) -> Dict[str, Any]:
        """Load data from source."""
        source = kwargs.get("source")
        analysis_type = kwargs.get("analysis_type", "exploratory")

        # Create sample data if file doesn't exist
        if source == "sales_data.csv" and not os.path.exists(source):
            sample_data = pd.DataFrame(
                {
                    "date": pd.date_range("2024-01-01", periods=100),
                    "product": ["Product A", "Product B", "Product C"] * 34
                    + ["Product A"],
                    "sales": [100 + i * 10 + (i % 3) * 50 for i in range(100)],
                    "region": ["North", "South", "East", "West"] * 25,
                }
            )
            sample_data.to_csv(source, index=False)

        try:
            if source.endswith(".csv"):
                df = pd.read_csv(source)
            elif source.endswith((".xlsx", ".xls")):
                df = pd.read_excel(source)
            else:
                return {"success": False, "error": "Unsupported file format"}

            return {
                "success": True,
                "data_info": {
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "dtypes": df.dtypes.to_dict(),
                    "sample_data": df.head().to_dict(),
                    "summary_stats": df.describe().to_dict(),
                },
                "message": f"Successfully loaded {source} for {analysis_type} analysis",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


class ExploreDataTool(BaseTool):
    """Tool for exploratory data analysis."""

    @property
    def name(self) -> str:
        return "explore_data"

    @property
    def description(self) -> str:
        return "Conduct exploratory data analysis"

    @property
    def args(self) -> Dict[str, ToolParameter]:
        return {
            "analysis_focus": ToolParameter(
                type="string",
                name="analysis_focus",
                description="Focus area for exploration (patterns, correlations, distributions)",
                required=False,
                default="patterns",
            )
        }

    async def async_execute(self, **kwargs) -> Dict[str, Any]:
        """Perform exploratory data analysis."""
        analysis_focus = kwargs.get("analysis_focus", "patterns")

        # Simulate exploratory analysis
        insights = {
            "patterns": {
                "trend": "Sales show an upward trend over time",
                "seasonality": "Weekly patterns detected with peaks on weekends",
                "outliers": "3 outliers identified in sales data",
            },
            "correlations": {
                "strong_correlation": "Sales and product category show 0.78 correlation",
                "weak_correlation": "Region and sales show 0.23 correlation",
            },
            "distributions": {
                "sales_distribution": "Right-skewed distribution with mean > median",
                "regional_distribution": "North region leads with 35% of total sales",
            },
        }

        return {
            "success": True,
            "insights": insights.get(analysis_focus, {}),
            "visualizations": [
                {"type": "line_chart", "title": "Sales Trend Over Time"},
                {"type": "bar_chart", "title": "Sales by Region"},
                {"type": "scatter_plot", "title": "Sales vs Product Category"},
            ],
            "message": f"Exploratory analysis completed with focus on {analysis_focus}",
        }


class CreateAnalysisPlanTool(BaseTool):
    """Tool for creating analysis plans."""

    @property
    def name(self) -> str:
        return "create_analysis_plan"

    @property
    def description(self) -> str:
        return "Create a systematic plan for data analysis"

    @property
    def args(self) -> Dict[str, ToolParameter]:
        return {
            "objective": ToolParameter(
                type="string",
                name="objective",
                description="Analysis objective or business question",
                required=True,
            ),
            "data_sources": ToolParameter(
                type="list",
                name="data_sources",
                description="List of data sources to use",
                required=False,
                default=[],
            ),
        }

    async def async_execute(self, **kwargs) -> Dict[str, Any]:
        """Create analysis plan."""
        objective = kwargs.get("objective", "")
        data_sources = kwargs.get("data_sources", [])

        # Create systematic analysis plan
        plan_steps = [
            {
                "step": 1,
                "action": "examine_data_sources",
                "description": "Identify and understand available data sources",
                "estimated_time": "5 minutes",
            },
            {
                "step": 2,
                "action": "load_data",
                "description": "Load and prepare data for analysis",
                "estimated_time": "10 minutes",
            },
            {
                "step": 3,
                "action": "explore_data",
                "description": "Conduct exploratory data analysis",
                "estimated_time": "15 minutes",
            },
            {
                "step": 4,
                "action": "statistical_analysis",
                "description": "Perform statistical tests and analysis",
                "estimated_time": "20 minutes",
            },
            {
                "step": 5,
                "action": "create_visualization",
                "description": "Generate charts and visualizations",
                "estimated_time": "15 minutes",
            },
            {
                "step": 6,
                "action": "generate_insights",
                "description": "Extract and present key insights",
                "estimated_time": "10 minutes",
            },
        ]

        return {
            "success": True,
            "plan": {
                "objective": objective,
                "data_sources": data_sources,
                "steps": plan_steps,
                "total_estimated_time": "75 minutes",
            },
            "message": f"Analysis plan created for objective: {objective}",
        }


async def demonstrate_data_agent():
    """Demonstrate the Data Analysis Planning Agent."""

    # Create tools
    tools = [
        DataSourceTool(),
        LoadDataTool(),
        ExploreDataTool(),
        CreateAnalysisPlanTool(),
    ]

    # Create tool pack
    tool_pack = ToolPack(tools=tools)

    # Create resource pack with tools
    resource_pack = ResourcePack()
    resource_pack._resources["tools"] = tool_pack

    # Create the data analysis planning agent
    agent = DataAnalysisPlanningAgent(
        resource=resource_pack,
        llm_client=None,  # You would provide an actual LLM client here
    )

    # Example 1: Sales trend analysis
    print("=" * 60)
    print("EXAMPLE 1: Sales Trend Analysis")
    print("=" * 60)

    question1 = "Analyze our sales data to identify trends and provide insights for business planning."
    message1 = AgentMessage(content=question1)

    try:
        # Simulate agent response (in real usage, this would involve LLM interaction)
        response1 = await simulate_agent_response(agent, message1)
        print(f"Agent Response: {response1}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Customer segmentation analysis
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Customer Segmentation Analysis")
    print("=" * 60)

    question2 = "Perform customer segmentation analysis to identify different customer groups and their characteristics."
    message2 = AgentMessage(content=question2)

    try:
        response2 = await simulate_agent_response(agent, message2)
        print(f"Agent Response: {response2}")
    except Exception as e:
        print(f"Error: {e}")


async def simulate_agent_response(
    agent: DataAnalysisPlanningAgent, message: AgentMessage
) -> str:
    """Simulate agent response for demonstration purposes."""

    # In a real implementation, this would involve:
    # 1. LLM processing the message and generating thoughts/actions
    # 2. Executing the actions using the tools
    # 3. Returning the results

    # For demonstration, we'll simulate the planning process
    question = message.content

    if "sales" in question.lower() and "trend" in question.lower():
        return """
Thought: I need to analyze sales data to identify trends. First, I should create a systematic analysis plan to ensure comprehensive coverage of the analysis requirements. Then I'll examine available data sources and proceed with the analysis step by step.

Action: create_analysis_plan
Action Input: {"objective": "Analyze sales data to identify trends and provide business insights", "data_sources": ["sales_data.csv"]}

Observation: Analysis plan created successfully with 6 steps estimated at 75 minutes total.

Thought: Now I'll examine the available data sources to understand the data structure and prepare for loading.

Action: examine_data_sources
Action Input: {"source_type": "file"}

Observation: Found 2 data sources: sales_data.csv (2.5MB) with columns [date, product, sales, region] and customer_data.xlsx (1.8MB).

Thought: Perfect! I found the sales data. Now I'll load it for exploratory analysis.

Action: load_data
Action Input: {"source": "sales_data.csv", "analysis_type": "exploratory"}

Observation: Successfully loaded sales_data.csv with shape (100, 4). Data includes date, product, sales, and region columns.

Thought: With the data loaded, I'll now conduct exploratory analysis to identify patterns and trends.

Action: explore_data
Action Input: {"analysis_focus": "patterns"}

Observation: Exploratory analysis completed. Key findings: Sales show upward trend over time, weekly patterns detected with weekend peaks, 3 outliers identified.

Action: terminate
Action Input: {"output": "Analysis Complete: Sales data shows clear upward trend with seasonal patterns. North region leads with 35% of sales. Recommendations: Focus marketing on weekend periods, investigate outliers for data quality, expand successful strategies in North region to other regions."}
        """
    elif "customer" in question.lower() and "segmentation" in question.lower():
        return """
Thought: I need to perform customer segmentation analysis. Let me start by creating a comprehensive analysis plan and then examine the available customer data.

Action: create_analysis_plan
Action Input: {"objective": "Perform customer segmentation analysis to identify customer groups", "data_sources": ["customer_data.xlsx"]}

Observation: Analysis plan created successfully with 6 steps for customer segmentation.

Thought: Now I'll examine the data sources to understand the customer data structure.

Action: examine_data_sources
Action Input: {"source_type": "file"}

Observation: Found customer_data.xlsx with columns [customer_id, name, email, segment].

Thought: I'll load the customer data to begin the segmentation analysis.

Action: load_data
Action Input: {"source": "customer_data.xlsx", "analysis_type": "statistical"}

Observation: Successfully loaded customer data with demographic and behavioral information.

Thought: Now I'll explore the data to identify natural customer segments and patterns.

Action: explore_data
Action Input: {"analysis_focus": "distributions"}

Observation: Customer analysis completed. Identified 4 main customer segments with distinct characteristics and behaviors.

Action: terminate
Action Input: {"output": "Customer Segmentation Complete: Identified 4 customer segments - 1) Premium Customers (15%, high value), 2) Regular Customers (45%, moderate value), 3) Occasional Customers (30%, low frequency), 4) New Customers (10%, recent acquisitions). Recommendations: Tailor marketing strategies by segment, focus retention on Premium segment, develop growth programs for Regular segment."}
        """
    else:
        return """
Thought: I need to understand this analysis request better and create an appropriate plan. Let me start by examining available data sources.

Action: examine_data_sources
Action Input: {}

Observation: Multiple data sources available. Please specify your analysis objective for better planning.

Action: terminate
Action Input: {"output": "Please provide a more specific analysis objective or business question so I can create a targeted analysis plan."}
        """


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(demonstrate_data_agent())
