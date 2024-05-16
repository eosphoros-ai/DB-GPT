import dataclasses
import logging
from typing import Any, List, Optional, Type, Union, cast

from dbgpt._private.config import Config
from dbgpt.agent.resource.database import DBParameters, RDBMSConnectorResource
from dbgpt.util import ParameterDescription

CFG = Config()

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class DatasourceDBParameters(DBParameters):
    """The DB parameters for the datasource."""

    db_name: str = dataclasses.field(metadata={"help": "DB name"})

    @classmethod
    def _resource_version(cls) -> str:
        """Return the resource version."""
        return "v1"

    @classmethod
    def to_configurations(
        cls,
        parameters: Type["DatasourceDBParameters"],
        version: Optional[str] = None,
    ) -> Any:
        """Convert the parameters to configurations."""
        conf: List[ParameterDescription] = cast(
            List[ParameterDescription], super().to_configurations(parameters)
        )
        version = version or cls._resource_version()
        if version != "v1":
            return conf
        # Compatible with old version
        for param in conf:
            if param.param_name == "db_name":
                return param.valid_values or []
        return []

    @classmethod
    def from_dict(
        cls, data: dict, ignore_extra_fields: bool = True
    ) -> "DatasourceDBParameters":
        """Create a new instance from a dictionary."""
        copied_data = data.copy()
        if "db_name" not in copied_data and "value" in copied_data:
            copied_data["db_name"] = copied_data.pop("value")
        return super().from_dict(copied_data, ignore_extra_fields=ignore_extra_fields)


class DatasourceResource(RDBMSConnectorResource):
    def __init__(self, name: str, db_name: Optional[str] = None, **kwargs):
        conn = CFG.local_db_manager.get_connector(db_name)
        super().__init__(name, connector=conn, db_name=db_name, **kwargs)

    @classmethod
    def resource_parameters_class(cls) -> Type[DatasourceDBParameters]:
        dbs = CFG.local_db_manager.get_db_list()
        results = [db["db_name"] for db in dbs]

        @dataclasses.dataclass
        class _DynDBParameters(DatasourceDBParameters):
            db_name: str = dataclasses.field(
                metadata={"help": "DB name", "valid_values": results}
            )

        return _DynDBParameters

    def get_schema_link(
        self, db: str, question: Optional[str] = None
    ) -> Union[str, List[str]]:
        """Return the schema link of the database."""
        try:
            from dbgpt.rag.summary.db_summary_client import DBSummaryClient
        except ImportError:
            raise ValueError("Could not import DBSummaryClient. ")
        client = DBSummaryClient(system_app=CFG.SYSTEM_APP)
        table_infos = None
        try:
            table_infos = client.get_db_summary(
                db,
                question,
                CFG.KNOWLEDGE_SEARCH_TOP_SIZE,
            )
        except Exception as e:
            logger.warning(f"db summary find error!{str(e)}")
        if not table_infos:
            conn = CFG.local_db_manager.get_connector(db)
            table_infos = conn.table_simple_info()

        return table_infos
