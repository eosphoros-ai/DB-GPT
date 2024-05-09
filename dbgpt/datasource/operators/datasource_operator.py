"""DatasourceOperator class.

Warning: This operator is in development and is not yet ready for production use.
"""

from typing import Any

from dbgpt.core.awel import MapOperator

from ..base import BaseConnector


class DatasourceOperator(MapOperator[str, Any]):
    """The Datasource Operator."""

    def __init__(self, connector: BaseConnector, **kwargs):
        """Create the datasource operator."""
        super().__init__(**kwargs)
        self._connector = connector

    async def map(self, input_value: str) -> Any:
        """Execute the query."""
        return await self.blocking_func_to_async(self.query, input_value)

    def query(self, input_value: str) -> Any:
        """Execute the query."""
        return self._connector.run_to_df(input_value)
