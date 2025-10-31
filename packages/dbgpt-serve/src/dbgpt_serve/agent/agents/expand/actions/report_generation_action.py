"""Report Generation Action for creating analysis reports."""

import json
import logging
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.agent import Action, ActionOutput, AgentResource, ResourceType
from dbgpt.vis.tags.vis_report_generation import Vis, VisReportGeneration

logger = logging.getLogger(__name__)


class ReportGenerationInput(BaseModel):
    """Report generation input model."""

    analysis_results: List[Dict[str, Any]] = Field(
        ...,
        description="List of analysis results from previous agents (anomaly detection, "
        "volatility analysis, etc.)",
    )
    user_question: str = Field(
        ...,
        description="The original user question or analysis request",
    )


class ReportGenerationAction(Action[ReportGenerationInput]):
    """Report generation action class."""

    def __init__(self, **kwargs):
        """Report generation action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisReportGeneration()

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
        return ReportGenerationInput

    @property
    def ai_out_schema(self) -> Optional[str]:
        """Return the AI output schema."""
        # For ReportGenerationAgent, we don't want to enforce a specific output schema
        # as it generates free-form markdown reports
        return None

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the report generation action."""

        try:
            # Prepare result data
            result_data = {"report_content": ai_message}

            # Create visualization
            view = None
            if self.render_protocol and need_vis_render:
                view = await self.render_protocol.display(content=ai_message)

            content = json.dumps(result_data, ensure_ascii=False)

            return ActionOutput(
                is_exe_success=True,
                content=content,
                view=view,
            )
        except Exception as e:
            logger.exception("Report generation failed!")
            return ActionOutput(
                is_exe_success=False,
                content=f"Error: Report generation failed! Reason: {str(e)}",
            )
