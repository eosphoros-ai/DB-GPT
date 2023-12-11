from typing import Any
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.task.base import IN, OUT
from dbgpt.datasource.base import BaseConnect


class DatasourceOperator(MapOperator[str, Any]):
    def __init__(self, connection: BaseConnect, **kwargs):
        super().__init__(**kwargs)
        self._connection = connection

    async def map(self, input_value: IN) -> OUT:
        return await self.blocking_func_to_async(self.query, input_value)

    def query(self, input_value: str) -> Any:
        return self._connection.run_to_df(input_value)
