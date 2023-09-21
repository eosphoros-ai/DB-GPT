from typing import Optional, Any
from pyspark.sql import SparkSession, DataFrame
from sqlalchemy import text

from pilot.connections.base import BaseConnect


class SparkConnect(BaseConnect):
    """Spark Connect
    Args:
    Usage:
    """

    """db type"""
    db_type: str = "spark"
    """db driver"""
    driver: str = "spark"
    """db dialect"""
    dialect: str = "sparksql"

    def __init__(
        self,
        file_path: str,
        spark_session: Optional[SparkSession] = None,
        engine_args: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Spark DataFrame from Datasource path
        return: Spark DataFrame
        """
        self.spark_session = (
            spark_session or SparkSession.builder.appName("dbgpt").getOrCreate()
        )
        self.path = file_path
        self.table_name = "temp"
        self.df = self.create_df(self.path)

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ):
        try:
            return cls(file_path=file_path, engine_args=engine_args)

        except Exception as e:
            print("load spark datasource error" + str(e))

    def create_df(self, path) -> DataFrame:
        """Create a Spark DataFrame from Datasource path
        return: Spark DataFrame
        """
        return self.spark_session.read.option("header", "true").csv(path)

    def run(self, sql):
        # self.log(f"llm ingestion sql query is :\n{sql}")
        # self.df = self.create_df(self.path)
        self.df.createOrReplaceTempView(self.table_name)
        df = self.spark_session.sql(sql)
        first_row = df.first()
        rows = [first_row.asDict().keys()]
        for row in df.collect():
            rows.append(row)
        return rows

    def query_ex(self, sql):
        rows = self.run(sql)
        field_names = rows[0]
        return field_names, rows

    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        return ""

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""

        return "ans"

    def get_fields(self):
        """Get column meta about dataframe."""
        return ",".join([f"({name}: {dtype})" for name, dtype in self.df.dtypes])

    def get_users(self):
        return []

    def get_grants(self):
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        return "UTF-8"

    def get_db_list(self):
        return ["default"]

    def get_db_names(self):
        return ["default"]

    def get_database_list(self):
        return []

    def get_database_names(self):
        return []

    def table_simple_info(self):
        return f"{self.table_name}{self.get_fields()}"

    def get_table_comments(self, db_name):
        return ""
