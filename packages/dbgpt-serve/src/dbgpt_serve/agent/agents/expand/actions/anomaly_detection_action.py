import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType
from dbgpt.vis.tags.vis_anomaly_detection import Vis, VisAnomalyDetection

logger = logging.getLogger(__name__)


class AnomalyDetectionInput(BaseModel):
    """Anomaly detection input model."""

    metric_name: str = Field(
        ...,
        description="The name of the metric being analyzed",
    )
    baseline_value: float = Field(
        ...,
        description="The baseline period value of the metric",
    )
    current_value: float = Field(
        ...,
        description="The current period value of the metric",
    )
    threshold: float = Field(
        ...,
        description="The threshold for determining anomalies (e.g., 0.1 for 10%)",
    )


class AnomalyDetectionAction(Action[AnomalyDetectionInput]):
    """Anomaly detection action class."""

    def __init__(self, **kwargs):
        """Anomaly detection action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisAnomalyDetection()

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
        return AnomalyDetectionInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the anomaly detection action."""
        try:
            param: AnomalyDetectionInput = self._input_convert(
                ai_message, AnomalyDetectionInput
            )
        except Exception as e:
            logger.exception(f"{str(e)}! \n {ai_message}")
            return ActionOutput(
                is_exe_success=False,
                content="Error: The answer is not output in the required format.",
            )

        try:
            if param.baseline_value == 0:
                fluctuation_rate = float("inf") if param.current_value > 0 else 0
            else:
                fluctuation_rate = (
                    param.current_value - param.baseline_value
                ) / param.baseline_value

            is_anomaly = False
            anomaly_type = "none"

            if abs(fluctuation_rate) > param.threshold:
                is_anomaly = True
                anomaly_type = "increase" if fluctuation_rate > 0 else "decrease"

            result_data = {
                "metric_name": param.metric_name,
                "baseline_value": param.baseline_value,
                "current_value": param.current_value,
                "fluctuation_rate": fluctuation_rate,
                "threshold": param.threshold,
                "is_anomaly": is_anomaly,
                "anomaly_type": anomaly_type,
                "recommend_next_step": "Proceed to volatility analysis"
                if is_anomaly
                else "No further analysis needed",
            }

            view = None
            if self.render_protocol and need_vis_render:
                view = await self.render_protocol.display(content=result_data)

            content = json.dumps(result_data, ensure_ascii=False)

            next_speakers = None
            if is_anomaly:
                from dbgpt_serve.agent.agents.expand.volatility_analysis_agent import (
                    VolatilityAnalysisAgent,
                )

                next_speakers = [VolatilityAnalysisAgent().role]
            else:
                from dbgpt_serve.agent.agents.expand.report_generation_agent import (
                    ReportGenerationAgent,
                )

                next_speakers = [ReportGenerationAgent().role]

            return ActionOutput(
                is_exe_success=True,
                content=content,
                view=view,
                next_speakers=next_speakers,
            )
        except Exception as e:
            logger.exception("Anomaly detection failed!")
            return ActionOutput(
                is_exe_success=False,
                content=f"Error: Anomaly detection failed! Reason: {str(e)}",
            )
