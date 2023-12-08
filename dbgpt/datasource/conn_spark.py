from typing import Optional, Any

from dbgpt.datasource.base import BaseConnect


class SparkConnect(BaseConnect):
    """
    Spark Connect supports operating on a variety of data sources through the DataFrame interface.
    A DataFrame can be operated on using relational transformations and can also be used to create a temporary view.
    Registering a DataFrame as a temporary view allows you to run SQL queries over its data.
    Datasource now support parquet, jdbc, orc, libsvm, csv, text, json.
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
        spark_session: Optional = None,
        engine_args: Optional[dict] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Spark DataFrame from Datasource path
        return: Spark DataFrame
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
    ):
        try:
            return cls(file_path=file_path, engine_args=engine_args)

        except Exception as e:
            print("load spark datasource error" + str(e))

    def create_df(self, path):
        """Create a Spark DataFrame from Datasource path(now support parquet, jdbc, orc, libsvm, csv, text, json.).
        return: Spark DataFrame
        reference:https://spark.apache.org/docs/latest/sql-data-sources-load-save-functions.html
        """
        extension = (
            "text" if path.rsplit(".", 1)[-1] == "txt" else path.rsplit(".", 1)[-1]
        )
        return self.spark_session.read.load(
            path, format=extension, inferSchema="true", header="true"
        )

    def run(self, sql):
        print(f"spark sql to run is {sql}")
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
