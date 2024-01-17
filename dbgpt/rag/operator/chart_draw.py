from typing import Any, Optional

from dbgpt.core.awel import MapOperator
from dbgpt.datasource.rdbms.base import RDBMSDatabase
from dbgpt.rag.schemalinker.chart_draw import ChartDraw


class ChartDrawOperator(MapOperator[Any, Any]):
    """The Chart Draw Operator."""

    def __init__(self, connection: Optional[RDBMSDatabase] = None, **kwargs):
        """
        Args:
        connection (RDBMSDatabase): The connection.
        """
        super().__init__(**kwargs)
        self._draw_chart = ChartDraw(connection=connection)

    def map(self, sql: str) -> str:
        """get sql result in db and draw.
        Args:
            sql (str): str.
        """
        return self._draw_chart.chart_draw(sql=sql)
