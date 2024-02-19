import json
import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from dbgpt.agent.actions.action import Action, ActionOutput, T
from dbgpt.agent.resource.resource_api import AgentResource, ResourceType
from dbgpt.agent.resource.resource_db_api import ResourceDbClient
from dbgpt.vis.tags.vis_dashboard import Vis, VisDashboard

logger = logging.getLogger(__name__)


class ChartItem(BaseModel):
    title: str = Field(
        ...,
        description="The title of the current analysis chart.",
    )
    display_type: str = Field(
        ...,
        description="The chart rendering method selected for SQL. If you don’t know what to output, just output 'response_table' uniformly.",
    )
    sql: str = Field(
        ..., description="Executable sql generated for the current target/problem"
    )
    thought: str = Field(..., description="Summary of thoughts to the user")


class DashboardAction(Action[List[ChartItem]]):
    def __init__(self):
        self._render_protocal = VisDashboard()

    @property
    def resource_need(self) -> Optional[ResourceType]:
        return ResourceType.DB

    @property
    def render_protocal(self) -> Optional[Vis]:
        return self._render_protocal

    @property
    def out_model_type(self):
        return List[ChartItem]

    async def a_run(
        self,
        ai_message: str,
        resource: Optional[AgentResource] = None,
        rely_action_out: Optional[ActionOutput] = None,
        need_vis_render: bool = True,
    ) -> ActionOutput:
        try:
            chart_items: List[ChartItem] = self._input_convert(
                ai_message, List[ChartItem]
            )
        except Exception as e:
            logger.exception(str(e))
            return ActionOutput(
                is_exe_success=False,
                content="The requested correctly structured answer could not be found.",
            )
        try:
            resource_db_client: ResourceDbClient = (
                self.resource_loader.get_resesource_api(self.resource_need)
            )
            if not resource_db_client:
                raise ValueError(
                    "There is no implementation class bound to database resource execution！"
                )

            chart_params = []
            for chart_item in chart_items:
                try:
                    sql_df = await resource_db_client.a_query_to_df(
                        resource.value, chart_item.sql
                    )
                    chart_dict = chart_item.dict()

                    chart_dict["data"] = sql_df
                except Exception as e:
                    logger.warn(f"Sql excute Failed！{str(e)}")
                    chart_dict["err_msg"] = str(e)
                chart_params.append(chart_dict)
            view = await self.render_protocal.disply(charts=chart_params)
            return ActionOutput(
                is_exe_success=True,
                content=json.dumps([chart_item.dict() for chart_item in chart_items]),
                view=view,
            )
        except Exception as e:
            logger.exception("Dashboard generate Failed！")
            return ActionOutput(
                is_exe_success=False, content=f"Dashboard action run failed!{str(e)}"
            )
