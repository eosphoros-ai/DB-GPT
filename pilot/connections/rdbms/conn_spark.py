import re
from typing import Optional, Any

from pyspark import SQLContext
from sqlalchemy import text

from pilot.connections.rdbms.base import RDBMSDatabase
from pyspark.sql import SparkSession, DataFrame

from sqlalchemy import create_engine


class SparkConnect:
    """Connect Spark
    Args:
    Usage:
    """

    """db type"""
    # db_type: str = "spark"
    """db driver"""
    driver: str = "spark"
    """db dialect"""
    # db_dialect: str = "spark"
    def __init__(
            self,
            spark_session: Optional[SparkSession] = None,
    ) -> None:
        self.spark_session = spark_session or SparkSession.builder.appName("dbgpt").master("local[*]").config("spark.sql.catalogImplementation", "hive").getOrCreate()

    def create_df(self, path)-> DataFrame:
        """load path into spark"""
        path = "/Users/chenketing/Downloads/Warehouse_and_Retail_Sales.csv"
        return self.spark_session.read.csv(path)

    def run(self, sql):
        self.spark_session.sql(sql)
        return sql.show()


    def get_indexes(self, table_name):
        """Get table indexes about specified table."""
        return ""

    def get_show_create_table(self, table_name):
        """Get table show create table about specified table."""
        session = self._db_sessions()
        cursor = session.execute(text(f"SHOW CREATE TABLE  {table_name}"))
        ans = cursor.fetchall()
        ans = ans[0][0]
        ans = re.sub(r"\s*ENGINE\s*=\s*MergeTree\s*", " ", ans, flags=re.IGNORECASE)
        ans = re.sub(
            r"\s*DEFAULT\s*CHARSET\s*=\s*\w+\s*", " ", ans, flags=re.IGNORECASE
        )
        ans = re.sub(r"\s*SETTINGS\s*\s*\w+\s*", " ", ans, flags=re.IGNORECASE)
        return ans

    def get_fields(self, df: DataFrame):
        """Get column fields about specified table."""
        return "\n".join([f"{name}: {dtype}" for name, dtype in df.dtypes])

    def get_users(self):
        return []

    def get_grants(self):
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        return "UTF-8"

    def get_database_list(self):
        return []

    def get_database_names(self):
        return []

    def get_table_comments(self, db_name):
        session = self._db_sessions()
        cursor = session.execute(
            text(
                f"""SELECT table, comment FROM system.tables WHERE database = '{db_name}'""".format(
                    db_name
                )
            )
        )
        table_comments = cursor.fetchall()
        return [
            (table_comment[0], table_comment[1]) for table_comment in table_comments
        ]


if __name__ == "__main__":
    # spark = SparkSession.builder \
    #     .appName("Spark-SQL and sqlalchemy") \
    #     .getOrCreate()
    db_url = "spark://B-V0ECMD6R-0244.local:7077"
    # engine = create_engine(db_url)
    # engine = create_engine("sparksql:///?Server=127.0.0.1")
    # sqlContext = SQLContext(spark)
    # df = sqlContext.read.format("jdbc").option("url", db_url).option("dbtable",
    #              "person").option(
    #     "user", "username").option("password", "password").load()
    spark = (
        SparkSession.builder.appName("ckt")
        .master("local[*]")
        # .config("hive.metastore.uris", "thrift://localhost:9083")
        # .config("spark.sql.warehouse.dir", "/Users/chenketing/myhive/")
        .config("spark.sql.catalogImplementation", "hive")
        .enableHiveSupport()
        .getOrCreate()
    )
    # sqlContext.read.jdbc(url='jdbc:hive2://127.0.0.1:10000/default', table='pokes', properties=connProps)

    # df = spark.read.format("jdbc").option("url", "jdbc:hive2://localhost:10000/dbgpt_test").option("dbtable", "dbgpt_test.dbgpt_table").option("driver", "org.apache.hive.jdbc.HiveDriver").load()

    path = "/Users/chenketing/Downloads/Warehouse_and_Retail_Sales.csv"
    df = spark.read.csv(path)
    df.createOrReplaceTempView("warehouse1")
    # df = spark.sql("show databases")
    # spark.sql("CREATE TABLE IF NOT EXISTS default.db_test (id INT, name STRING)")
    # df = spark.sql("DESC default.db_test")
    # spark.sql("INSERT INTO default.db_test VALUES (1, 'Alice')")
    # spark.sql("INSERT INTO default.db_test VALUES (2, 'Bob')")
    # spark.sql("INSERT INTO default.db_test VALUES (3, 'Charlie')")
    # df = spark.sql("select * from default.db_test")
    print(spark.sql("SELECT * FROM warehouse1 limit 5").show())

    # connection = engine.connect()

    # 执行Spark SQL查询
    # result = connection.execute("SELECT * FROM warehouse")
