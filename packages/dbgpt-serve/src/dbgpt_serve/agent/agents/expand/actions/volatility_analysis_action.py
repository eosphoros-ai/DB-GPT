"""Volatility Analysis Action for performing attribution analysis."""

import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType
from dbgpt.agent.core.agent import AgentMessage
from dbgpt.component import ComponentType
from dbgpt.vis.tags.vis_volatility_analysis import Vis, VisVolatilityAnalysis

logger = logging.getLogger(__name__)


class VolatilityAnalysisInput(BaseModel):
    """Volatility analysis input model."""

    metric_name: str = Field(
        ...,
        description="The name of the metric being analyzed",
    )
    baseline_total: float = Field(
        ...,
        description="The baseline period total value of the metric",
    )
    current_total: float = Field(
        ...,
        description="The current period total value of the metric",
    )
    baseline_time_range: str = Field(
        ...,
        description="The baseline time range for the metric analysis",
    )
    current_time_range: str = Field(
        ...,
        description="The current time range for the metric analysis",
    )
    dimension: str = Field(
        ...,
        description="Selected dimension for attribution analysis. If the metric has "
        "multiple dimensions available for analysis, only one needs to be selected.",
    )


class VolatilityAnalysisAction(Action[VolatilityAnalysisInput]):
    """Volatility analysis action class."""

    def __init__(self, **kwargs):
        """Volatility analysis action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisVolatilityAnalysis()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return None

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Return the output model type."""
        return VolatilityAnalysisInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the volatility analysis action."""
        try:
            param: VolatilityAnalysisInput = self._input_convert(
                ai_message, VolatilityAnalysisInput
            )
        except Exception as e:
            logger.exception(f"{str(e)}! \n {ai_message}")
            return ActionOutput(
                is_exe_success=False,
                content="Error: The answer is not output in the required format.",
            )

        try:
            from dbgpt._private.config import Config
            from dbgpt.agent import AgentContext, AgentMemory, LLMConfig
            from dbgpt.agent.core.agent_manage import get_agent_manager
            from dbgpt.agent.resource import get_resource_manager
            from dbgpt.agent.util.llm.llm import LLMStrategyType
            from dbgpt.core import ModelMessageRoleType
            from dbgpt.model.cluster import WorkerManagerFactory
            from dbgpt.model.cluster.client import DefaultLLMClient
            from dbgpt.util.executor_utils import blocking_func_to_async

            agent_manager = get_agent_manager()
            data_scientist_cls = agent_manager.get_by_name("DataScientist")

            context = AgentContext(
                conv_id=f"volatility_analysis_{param.metric_name}_{param.dimension}"
            )
            agent_memory = AgentMemory()
            agent_memory.gpts_memory.init(conv_id=context.conv_id)

            CFG = Config()
            worker_manager = CFG.SYSTEM_APP.get_component(
                ComponentType.WORKER_MANAGER_FACTORY, WorkerManagerFactory
            ).create()
            llm_provider = DefaultLLMClient(worker_manager, auto_convert_message=True)

            llm_config = LLMConfig(
                llm_client=llm_provider,
                llm_strategy=LLMStrategyType.Priority,
                strategy_context=None,
            )

            depend_resource = None
            if self.resource:
                depend_resource = self.resource
            else:
                rm = get_resource_manager()
                try:
                    depend_resource = await blocking_func_to_async(
                        CFG.SYSTEM_APP, rm.build_resource, []
                    )
                except Exception as e:
                    logger.warning(f"Failed to build resource: {e}")
                    depend_resource = None

            data_scientist = (
                await data_scientist_cls()
                .bind(context)
                .bind(llm_config)
                .bind(depend_resource)
                .bind(agent_memory)
                .build()
            )

            schema_info = ""
            if depend_resource:
                try:
                    schema_info = depend_resource.get_schema_link(
                        depend_resource._db_name
                    )
                except Exception as e:
                    logger.warning(f"Failed to get schema info: {e}")
                    schema_info = "Schema information not available"

            factor_query_content = (
                f"Please generate SQL to get all distinct values of the dimension "
                f"'{param.dimension}' for the metric '{param.metric_name}'.\n\n"
                f"Database Schema Information:\n{schema_info}"
            )
            factor_query_message = AgentMessage(
                content=factor_query_content,
                role=ModelMessageRoleType.HUMAN,
            )

            factor_response = await data_scientist.generate_reply(
                received_message=factor_query_message,
                sender=data_scientist,
            )
            factors = []
            if (
                factor_response
                and factor_response.action_report
                and factor_response.action_report.is_exe_success
            ):
                try:
                    action_content = json.loads(factor_response.action_report.content)
                    if "data" in action_content:
                        for row in action_content["data"]:
                            if isinstance(row, dict):
                                factor = list(row.values())[0]
                                factors.append(factor)
                            elif isinstance(row, list):
                                factors.append(row[0])
                except Exception as e:
                    logger.warning(
                        f"Failed to parse factors from DataScientist response: {e}"
                    )

            factor_data = []
            for factor in factors:
                baseline_query = (
                    f"Please generate SQL to get the baseline value of metric "
                    f"'{param.metric_name}' for {param.dimension}='{factor}' "
                    f"during the "
                    f"baseline time range ({param.baseline_time_range}).\n\n"
                    f"Database Schema Information:\n{schema_info}"
                )
                baseline_message = AgentMessage(
                    content=baseline_query,
                    role=ModelMessageRoleType.HUMAN,
                )

                baseline_response = await data_scientist.generate_reply(
                    received_message=baseline_message,
                    sender=data_scientist,
                )

                baseline_value = 0.0
                if (
                    baseline_response
                    and baseline_response.action_report
                    and baseline_response.action_report.is_exe_success
                ):
                    try:
                        action_content = json.loads(
                            baseline_response.action_report.content
                        )
                        if "data" in action_content and action_content["data"]:
                            row = action_content["data"][0]
                            if isinstance(row, dict):
                                baseline_value = list(row.values())[0]
                            elif isinstance(row, list):
                                baseline_value = row[0]
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse baseline value for factor {factor}: {e}"
                        )
                current_query = (
                    f"Please generate SQL to get the current value of metric "
                    f"'{param.metric_name}' for {param.dimension}='{factor}' "
                    f"during the "
                    f"current time range ({param.current_time_range}).\n\n"
                    f"Database Schema Information:\n{schema_info}"
                )
                current_message = AgentMessage(
                    content=current_query,
                    role=ModelMessageRoleType.HUMAN,
                )

                current_response = await data_scientist.generate_reply(
                    received_message=current_message,
                    sender=data_scientist,
                )

                current_value = 0.0
                if (
                    current_response
                    and current_response.action_report
                    and current_response.action_report.is_exe_success
                ):
                    try:
                        action_content = json.loads(
                            current_response.action_report.content
                        )
                        if "data" in action_content and action_content["data"]:
                            row = action_content["data"][0]
                            if isinstance(row, dict):
                                current_value = list(row.values())[0]
                            elif isinstance(row, list):
                                current_value = row[0]
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse current value for factor {factor}: {e}"
                        )

                factor_data.append(
                    {
                        "factor": factor,
                        "baseline_value": float(baseline_value),
                        "current_value": float(current_value),
                    }
                )

            total_baseline = param.baseline_total
            total_current = param.current_total
            total_change = total_current - total_baseline

            for factor_info in factor_data:
                baseline_val = factor_info["baseline_value"]
                current_val = factor_info["current_value"]
                absolute_change = current_val - baseline_val
                if total_change != 0:
                    contribution_rate = absolute_change / total_change
                else:
                    contribution_rate = 0.0

                factor_info["absolute_change"] = absolute_change
                factor_info["contribution_rate"] = contribution_rate

            factor_data.sort(key=lambda x: x["contribution_rate"], reverse=True)
            result_data = {
                "metric_name": param.metric_name,
                "dimension": param.dimension,
                "baseline_total": total_baseline,
                "current_total": total_current,
                "total_change": total_change,
                "factors": factor_data,
            }

            view = None
            if self.render_protocol and need_vis_render:
                view = await self.render_protocol.display(content=result_data)

            content = json.dumps(result_data, ensure_ascii=False)

            return ActionOutput(
                is_exe_success=True,
                content=content,
                view=view,
            )
        except Exception as e:
            logger.exception("Volatility analysis failed!")
            return ActionOutput(
                is_exe_success=False,
                content=f"Error: Volatility analysis failed! Reason: {str(e)}",
            )
