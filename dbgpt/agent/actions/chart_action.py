"""Chart Action for SQL execution and rendering."""
import json
import logging
from typing import Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.vis.tags.vis_chart import Vis, VisChart

from ..resource.resource_api import AgentResource, ResourceType
from ..resource.resource_db_api import ResourceDbClient
from .action import Action, ActionOutput

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

    def __init__(self):
        """Create a chart action."""
        super().__init__()
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
                content="The requested correctly structured answer could not be found.",
            )
        try:
            if not self.resource_loader:
                raise ValueError("ResourceLoader is not initialized！")
            resource_db_client: Optional[
                ResourceDbClient
            ] = self.resource_loader.get_resource_api(
                self.resource_need, ResourceDbClient
            )
            if not resource_db_client:
                raise ValueError(
                    "There is no implementation class bound to database resource "
                    "execution！"
                )
            if not resource:
                raise ValueError("The data resource is not found！")
            data_df = await resource_db_client.query_to_df(resource.value, param.sql)
            if not self.render_protocol:
                raise ValueError("The rendering protocol is not initialized！")
            view = await self.render_protocol.display(
                chart=json.loads(param.json()), data_df=data_df
            )
            if not self.resource_need:
                raise ValueError("The resource type is not found！")
            return ActionOutput(
                is_exe_success=True,
                content=param.json(),
                view=view,
                resource_type=self.resource_need.value,
                resource_value=resource.value,
            )
        except Exception as e:
            logger.exception("Check your answers, the sql run failed！")
            return ActionOutput(
                is_exe_success=False,
                content=f"Check your answers, the sql run failed!Reason:{str(e)}",
            )
