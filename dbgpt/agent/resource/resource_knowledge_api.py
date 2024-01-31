from typing import Any, Dict, List, Optional, Tuple, Union

from .resource_api import ResourceClient, ResourceType


class ResourceDbClient(ResourceClient):
    @property
    def type(self):
        return ResourceType.Knowledge

    async def a_get_schema_link(
        self, db_name: str, question: Optional[str] = None
    ) -> str:
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def a_query_to_df(self, db_name: str, sql: str):
        raise NotImplementedError("The run method should be implemented in a subclass.")

    async def a_run_sql(self, db_name: str, sql: str):
        raise NotImplementedError("The run method should be implemented in a subclass.")
