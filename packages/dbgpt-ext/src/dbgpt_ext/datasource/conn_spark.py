"""Spark Connector."""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional, Type

from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    ResourceCategory,
    auto_register_resource,
)
from dbgpt.datasource.base import BaseConnector
from dbgpt.datasource.parameter import BaseDatasourceParameters
from dbgpt.util.i18n_utils import _

if TYPE_CHECKING:
    from pyspark.sql import SparkSession
logger = logging.getLogger(__name__)


@auto_register_resource(
    label=_("Apache Spark datasource"),
    category=ResourceCategory.DATABASE,
    tags={"order": TAGS_ORDER_HIGH},
    description=_("Unified engine for large-scale data analytics."),
)
@dataclass
class SparkParameters(BaseDatasourceParameters):
    """Spark connection parameters."""

    __type__ = "spark"
    path: str = field(
        metadata={
            "help": _("The file path of the data source."),
        },
    )

    def create_connector(self) -> "SparkConnector":
        """Create Spark connector."""
        return SparkConnector.from_parameters(self)

    def db_url(self, ssl=False, charset=None):
        raise NotImplementedError("Spark does not support db_url")


class SparkConnector(BaseConnector):
    """Spark Connector.

    Spark Connect supports operating on a variety of data sources through the DataFrame
    interface.
    A DataFrame can be operated on using relational transformations and can also be
    used to create a temporary view.Registering a DataFrame as a temporary view allows
    you to run SQL queries over its data.

    Datasource now support parquet, jdbc, orc, libsvm, csv, text, json.
    """

    """db type"""
    db_type: str = "spark"
    """db driver"""
    driver: str = "spark"
    """db dialect"""
    dialect: str = "sparksql"

    @classmethod
    def param_class(cls) -> Type[SparkParameters]:
        """Return the parameter class."""
        return SparkParameters

    @classmethod
    def from_parameters(cls, parameters: SparkParameters) -> "SparkConnector":
        """Create a new SparkConnector from parameters."""
        return cls(file_path=parameters.path)

    def __init__(
        self,
        file_path: str,
        spark_session: Optional["SparkSession"] = None,
        **kwargs: Any,
    ) -> None:
        """Create a Spark Connector.

        Args:
            file_path: file path
            spark_session: spark session
            kwargs: other args
        """
        from pyspark.sql import SparkSession

        self.spark_session = (
            spark_session or SparkSession.builder.appName("dbgpt_spark").getOrCreate()
        )
        self.path = file_path
        self.table_name = "temp"
        self.df = self.create_df(self.path)

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> "SparkConnector":
        """Create a new SparkConnector from file path."""
        try:
            return cls(file_path=file_path, engine_args=engine_args, **kwargs)

        except Exception as e:
            logger.error("load spark datasource error" + str(e))
            raise e

    def create_df(self, path):
        """Create a Spark DataFrame.

        Create a Spark DataFrame from Datasource path(now support parquet, jdbc,
        orc, libsvm, csv, text, json.).

        return: Spark DataFrame
        reference:https://spark.apache.org/docs/latest/sql-data-sources-load-save-functions.html
        """
        extension = (
            "text" if path.rsplit(".", 1)[-1] == "txt" else path.rsplit(".", 1)[-1]
        )
        return self.spark_session.read.load(
            path, format=extension, inferSchema="true", header="true"
        )

    def run(self, sql: str, fetch: str = "all"):
        """Execute sql command."""
        logger.info(f"spark sql to run is {sql}")
        self.df.createOrReplaceTempView(self.table_name)
        df = self.spark_session.sql(sql)
        first_row = df.first()
        rows = [first_row.asDict().keys()]
        for row in df.collect():
            rows.append(row)
        return rows

    def query_ex(self, sql: str, timeout: Optional[float] = None):
        """Execute sql command."""
        rows = self.run(sql)
        field_names = rows[0]
        return field_names, rows

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        return ""

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        return "ans"

    def get_fields(self, table_name: str):
        """Get column meta about dataframe.

        TODO: Support table_name.
        """
        return ",".join([f"({name}: {dtype})" for name, dtype in self.df.dtypes])

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_db_names(self):
        """Get database names."""
        return ["default"]

    def get_database_names(self):
        """Get database names."""
        return []

    def table_simple_info(self):
        """Get table simple info."""
        return f"{self.table_name}{self.get_fields()}"

    def get_table_comments(self, db_name):
        """Get table comments."""
        return ""
