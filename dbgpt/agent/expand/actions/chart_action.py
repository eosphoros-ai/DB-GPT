"""Chart Action for SQL execution and rendering."""

import json
import logging
from typing import List, Optional

from dbgpt._private.pydantic import BaseModel, Field, model_to_json
from dbgpt.vis.tags.vis_chart import Vis, VisChart

from ...core.action.base import Action, ActionOutput
from ...resource.base import AgentResource, ResourceType
from ...resource.database import DBResource

logger = logging.getLogger(__name__)


class SqlInput(BaseModel):
    """SQL input model."""

    display_type: str = Field(
        ...,
        description="The chart rendering method selected for SQL. If you don’t know "
        "what to output, just output 'response_table' uniformly.",
    )
    sql: str = Field(
        ..., description="Executable sql generated for the current target/problem"
    )
    thought: str = Field(..., description="Summary of thoughts to the user")


class ChartAction(Action[SqlInput]):
    """Chart action class."""

    def __init__(self, **kwargs):
        """Chart action init."""
        super().__init__(**kwargs)
        self._render_protocol = VisChart()

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
        return SqlInput

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
            param: SqlInput = self._input_convert(ai_message, SqlInput)
        except Exception as e:
            logger.exception(f"{str(e)}! \n {ai_message}")
            return ActionOutput(
                is_exe_success=False,
                content="Error:The answer is not output in the required format.",
            )
        try:
            if not self.resource_need:
                raise ValueError("The resource type is not found！")

            if not self.render_protocol:
                raise ValueError("The rendering protocol is not initialized！")

            db_resources: List[DBResource] = DBResource.from_resource(self.resource)
            if not db_resources:
                raise ValueError("The database resource is not found！")

            db = db_resources[0]
            data_df = await db.query_to_df(param.sql)
            view = await self.render_protocol.display(
                chart=json.loads(model_to_json(param)), data_df=data_df
            )

            return ActionOutput(
                is_exe_success=True,
                content=model_to_json(param),
                view=view,
                resource_type=self.resource_need.value,
                resource_value=db._db_name,
            )
        except Exception as e:
            logger.exception("Check your answers, the sql run failed！")
            return ActionOutput(
                is_exe_success=False,
                content=f"Error:Check your answers, the sql run failed!Reason:{str(e)}",
            )
