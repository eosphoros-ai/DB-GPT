"""Dashboard Action Module."""

import json
import logging
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict
from dbgpt.vis.tags.vis_dashboard import Vis, VisDashboard

from ...core.action.base import Action, ActionOutput
from ...resource.base import AgentResource, ResourceType
from ...resource.database import DBResource

logger = logging.getLogger(__name__)


class ChartItem(BaseModel):
    """Chart item model."""

    title: str = Field(
        ...,
        description="The title of the current analysis chart.",
    )
    display_type: str = Field(
        ...,
        description="The chart rendering method selected for SQL. If you don’t know "
        "what to output, just output 'response_table' uniformly.",
    )
    sql: str = Field(
        ..., description="Executable sql generated for the current target/problem"
    )
    thought: str = Field(..., description="Summary of thoughts to the user")

    def to_dict(self):
        """Convert to dict."""
        return model_to_dict(self)


class DashboardAction(Action[List[ChartItem]]):
    """Dashboard action class."""

    def __init__(self, **kwargs):
        """Dashboard action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisDashboard()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        """Return the resource type needed for the action."""
        return ResourceType.DB

    @property
    def render_protocol(self) -> Optional[Vis]:
        """Return the render protocol."""
        return self._render_protocol

    @property
    def out_model_type(self):
        """Return the output model type."""
        return List[ChartItem]

    async def run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
        **kwargs,
    ) -> ActionOutput:
        """Perform the action."""
        try:
            input_param = self._input_convert(ai_message, List[ChartItem])
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )
        if not isinstance(input_param, list):
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )
        chart_items: List[ChartItem] = input_param
        try:
            db_resources: List[DBResource] = DBResource.from_resource(self.resource)
            if not db_resources:
                raise ValueError("The database resource is not found！")

            db = db_resources[0]

            if not db:
                raise ValueError("The database resource is not found！")

            chart_params = []
            for chart_item in chart_items:
                chart_dict = {}
                try:
                    sql_df = await db.query_to_df(chart_item.sql)
                    chart_dict = chart_item.to_dict()

                    chart_dict["data"] = sql_df
                except Exception as e:
                    logger.warning(f"Sql execute failed！{str(e)}")
                    chart_dict["err_msg"] = str(e)
                chart_params.append(chart_dict)
            if not self.render_protocol:
                raise ValueError("The render protocol is not initialized!")
            view = await self.render_protocol.display(charts=chart_params)
            return ActionOutput(
                is_exe_success=True,
                content=json.dumps(
                    [chart_item.to_dict() for chart_item in chart_items]
                ),
                view=view,
            )
        except Exception as e:
            logger.exception("Dashboard generate Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Dashboard action run failed!{str(e)}"
            )
