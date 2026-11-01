"""Chart Action for SQL execution and rendering."""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict, model_to_json
from dbgpt.vis.tags.vis_chart import Vis, VisChart

from ....core.interface.report_capture import (
    capture_chart_execution,
    capture_sql_execution,
)
from ...core.action.base import Action, ActionOutput
from ...resource.base import AgentResource, ResourceType
from ...resource.database import DBResource

logger = logging.getLogger(__name__)


def _native_vis_chart_spec(view: Optional[str]) -> Optional[Dict[str, Any]]:
    """Extract the structured native-chart payload from a VisChart response.

    ``VisChart`` returns a fenced ``vis-db-chart`` block for the web client's
    native renderer.  Capturing that JSON, rather than just the display type,
    lets a persisted report replay the exact chart without an iframe or a
    second chart-generation implementation.
    """
    if not view:
        return None
    match = re.search(r"```vis-db-chart\s*(\{.*?\})\s*```", view, re.DOTALL)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(1))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("type"), str):
        return None
    return {"renderer": "vis-db-chart", **payload}


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _capture_sql_dataframe(param: "SqlInput", db, data_df, duration_ms: int):
    return capture_sql_execution(
        sql=param.sql,
        database=str(getattr(db, "_db_name", "")) or None,
        duration_ms=duration_ms,
        columns=[str(column) for column in data_df.columns],
        rows=data_df.itertuples(index=False, name=None),
        action="chart_action.query",
        display_type=param.display_type,
    )


def _capture_sql_failure(param: "SqlInput", db, duration_ms: int, error: str):
    return capture_sql_execution(
        sql=param.sql,
        database=str(getattr(db, "_db_name", "")) or None,
        duration_ms=duration_ms,
        error=error,
        action="chart_action.query",
        display_type=param.display_type,
    )


def _capture_chart_render(
    param: "SqlInput",
    sql_artifact_id: Optional[str],
    duration_ms: int,
    *,
    view: Optional[str] = None,
    error: Optional[str] = None,
    spec: Optional[Dict[str, Any]] = None,
):
    if sql_artifact_id is None:
        return None
    return capture_chart_execution(
        input_artifact_ids=[sql_artifact_id],
        action="chart_action.render",
        duration_ms=duration_ms,
        error=error,
        chart_type=param.display_type,
        spec=spec or {"display_type": param.display_type},
        output_inline=view,
        media_type="application/vnd.dbgpt.vis+json",
    )


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
            query_started = time.perf_counter()
            try:
                data_df = await db.query_to_df(param.sql)
            except Exception as error:
                _capture_sql_failure(
                    param,
                    db,
                    _elapsed_ms(query_started),
                    str(error) or type(error).__name__,
                )
                raise
            sql_artifact_id = _capture_sql_dataframe(
                param, db, data_df, _elapsed_ms(query_started)
            )
            render_started = time.perf_counter()
            try:
                view = await self.render_protocol.display(
                    chart=json.loads(model_to_json(param)), data_df=data_df
                )
            except Exception as error:
                _capture_chart_render(
                    param,
                    sql_artifact_id,
                    _elapsed_ms(render_started),
                    error=str(error) or type(error).__name__,
                )
                raise
            _capture_chart_render(
                param,
                sql_artifact_id,
                _elapsed_ms(render_started),
                view=view,
                spec=_native_vis_chart_spec(view),
            )

            param_dict = model_to_dict(param)
            if not data_df.empty:
                param_dict["count"] = len(data_df)

                param_dict["data"] = json.loads(
                    data_df.to_json(
                        orient="records",
                        force_ascii=False,
                        date_format="iso",
                        date_unit="s",
                    )
                )

            content = json.dumps(param_dict, ensure_ascii=False)

            return ActionOutput(
                is_exe_success=True,
                content=content,
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
