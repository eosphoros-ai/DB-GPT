"""Metric Info Action for retrieving specific metric information."""

import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType

logger = logging.getLogger(__name__)


class MetricInfoInput(BaseModel):
    metric_name: str = Field(
        ...,
        description="The name of the metric to retrieve information for (required)",
    )

    field_name: str = Field(
        ...,
        description="The field name of the metric (required)",
    )

    calculation_rule: Optional[str] = Field(
        None,
        description="The calculation rule for the metric (optional)",
    )

    suggested_dimension: Optional[str] = Field(
        None,
        description="The suggested calculation dimension for the metric "
        "(optional, max one)",
    )

    threshold: Optional[float] = Field(
        None,
        description="The threshold value for the metric (optional)",
    )


class MetricInfoAction(Action[MetricInfoInput]):
    """Metric info action class."""

    def __init__(self, **kwargs):
        """Metric info action init."""
        super().__init__(**kwargs)

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return None

    @property
    def out_model_type(self):
        """Return the output model type."""
        return MetricInfoInput

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the metric info retrieval action."""
        try:
            param: MetricInfoInput = self._input_convert(ai_message, MetricInfoInput)
        except Exception as e:
            logger.exception(f"{str(e)}! \n {ai_message}")
            return ActionOutput(
                is_exe_success=False,
                content="Error: The answer is not output in the required format.",
            )

        try:
            result_data = {
                "metric_name": param.metric_name,
                "field_name": param.field_name,
                "calculation_rule": param.calculation_rule,
                "suggested_dimension": param.suggested_dimension,
                "threshold": param.threshold,
            }

            content = json.dumps(result_data, ensure_ascii=False)

            next_speakers = None

            return ActionOutput(
                is_exe_success=True,
                content=content,
                next_speakers=next_speakers,
            )
        except Exception as e:
            logger.exception("Metric info retrieval failed!")
            return ActionOutput(
                is_exe_success=False,
                content=f"Error: Metric info retrieval failed! Reason: {str(e)}",
            )
