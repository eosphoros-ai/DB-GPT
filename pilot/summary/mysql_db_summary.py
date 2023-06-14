import json

from pilot.configs.config import Config
from pilot.summary.db_summary import DBSummary, TableSummary, FieldSummary, IndexSummary

CFG = Config()

# {
#     "database_name": "mydatabase",
#     "tables": [
#         {
#             "table_name": "customers",
#             "columns": [
#                 {"name": "id", "type": "int(11)", "is_primary_key": true},
#                 {"name": "name", "type": "varchar(255)", "is_primary_key": false},
#                 {"name": "email", "type": "varchar(255)", "is_primary_key": false}
#             ],
#             "indexes": [
#                 {"name": "PRIMARY", "type": "primary", "columns": ["id"]},
#                 {"name": "idx_name", "type": "index", "columns": ["name"]},
#                 {"name": "idx_email", "type": "index", "columns": ["email"]}
#             ],
#             "size_in_bytes": 1024,
#             "rows": 1000
#         },
#         {
#             "table_name": "orders",
#             "columns": [
#                 {"name": "id", "type": "int(11)", "is_primary_key": true},
#                 {"name": "customer_id", "type": "int(11)", "is_primary_key": false},
#                 {"name": "order_date", "type": "date", "is_primary_key": false},
#                 {"name": "total_amount", "type": "decimal(10,2)", "is_primary_key": false}
#             ],
#             "indexes": [
#                 {"name": "PRIMARY", "type": "primary", "columns": ["id"]},
#                 {"name": "fk_customer_id", "type": "foreign_key", "columns": ["customer_id"], "referenced_table": "customers", "referenced_columns": ["id"]}
#             ],
#             "size_in_bytes": 2048,
#             "rows": 500
#         }
#     ],
#     "qps": 100,
#     "tps": 50
# }


class MysqlSummary(DBSummary):
    """Get mysql summary template."""

    def __init__(self, name):
        self.name = name
        self.type = "MYSQL"
        self.summery = """{{"database_name": "{name}", "type": "{type}", "tables": "{tables}", "qps": "{qps}", "tps": {tps}}}"""
        self.tables = {}
        self.tables_info = []
        self.vector_tables_info = []
        # self.tables_summary = {}

        self.db = CFG.local_db
        self.db.get_session(name)

        self.metadata = """user info :{users}, grant info:{grant}, charset:{charset}, collation:{collation}""".format(
            users=self.db.get_users(),
            grant=self.db.get_grants(),
            charset=self.db.get_charset(),
            collation=self.db.get_collation(),
        )
        tables = self.db.get_table_names()
        self.table_comments = self.db.get_table_comments(name)
        comment_map = {}
        for table_comment in self.table_comments:
            self.tables_info.append(
                "table name:{table_name},table description:{table_comment}".format(
                    table_name=table_comment[0], table_comment=table_comment[1]
                )
            )
            comment_map[table_comment[0]] = table_comment[1]

            vector_table = json.dumps(
                {"table_name": table_comment[0], "table_description": table_comment[1]}
            )
            self.vector_tables_info.append(
                vector_table.encode("utf-8").decode("unicode_escape")
            )
        self.table_columns_info = []
        self.table_columns_json = []

        for table_name in tables:
            table_summary = MysqlTableSummary(self.db, name, table_name, comment_map)
            # self.tables[table_name] = table_summary.get_summery()
            self.tables[table_name] = table_summary.get_columns()
            self.table_columns_info.append(table_summary.get_columns())
            # self.table_columns_json.append(table_summary.get_summary_json())
            table_profile = (
                "table name:{table_name},table description:{table_comment}".format(
                    table_name=table_name,
                    table_comment=self.db.get_show_create_table(table_name),
                )
            )
            self.table_columns_json.append(table_profile)
            # self.tables_info.append(table_summary.get_summery())

    def get_summery(self):
        if CFG.SUMMARY_CONFIG == "FAST":
            return self.vector_tables_info
        else:
            return self.summery.format(
                name=self.name, type=self.type, table_info=";".join(self.tables_info)
            )

    def get_db_summery(self):
        return self.summery.format(
            name=self.name,
            type=self.type,
            tables=";".join(self.vector_tables_info),
            qps=1000,
            tps=1000,
        )

    def get_table_summary(self):
        return self.tables

    def get_table_comments(self):
        return self.table_comments

    def table_info_json(self):
        return self.table_columns_json


class MysqlTableSummary(TableSummary):
    """Get mysql table summary template."""

    def __init__(self, instance, dbname, name, comment_map):
        self.name = name
        self.dbname = dbname
        self.summery = """database name:{dbname}, table name:{name}, have columns info: {fields}, have indexes info: {indexes}"""
        self.json_summery_template = """{{"table_name": "{name}", "comment": "{comment}", "columns": "{fields}", "indexes": "{indexes}", "size_in_bytes": {size_in_bytes},  "rows": {rows}}}"""
        self.fields = []
        self.fields_info = []
        self.indexes = []
        self.indexes_info = []
        self.db = instance
        fields = self.db.get_fields(name)
        indexes = self.db.get_indexes(name)
        field_names = []
        for field in fields:
            field_summary = MysqlFieldsSummary(field)
            self.fields.append(field_summary)
            self.fields_info.append(field_summary.get_summery())
            field_names.append(field[0])

        self.column_summery = """{name}({columns_info})""".format(
            name=name, columns_info=",".join(field_names)
        )

        for index in indexes:
            index_summary = MysqlIndexSummary(index)
            self.indexes.append(index_summary)
            self.indexes_info.append(index_summary.get_summery())

        self.json_summery = self.json_summery_template.format(
            name=name,
            comment=comment_map[name],
            fields=self.fields_info,
            indexes=self.indexes_info,
            size_in_bytes=1000,
            rows=1000,
        )

    def get_summery(self):
        return self.summery.format(
            name=self.name,
            dbname=self.dbname,
            fields=";".join(self.fields_info),
            indexes=";".join(self.indexes_info),
        )

    def get_columns(self):
        return self.column_summery

    def get_summary_json(self):
        return self.json_summery


class MysqlFieldsSummary(FieldSummary):
    """Get mysql field summary template."""

    def __init__(self, field):
        self.name = field[0]
        # self.summery = """column name:{name}, column data type:{data_type}, is nullable:{is_nullable}, default value is:{default_value}, comment is:{comment} """
        # self.summery = """{"name": {name}, "type": {data_type}, "is_primary_key": {is_nullable}, "comment":{comment}, "default":{default_value}}"""
        self.data_type = field[1]
        self.default_value = field[2]
        self.is_nullable = field[3]
        self.comment = field[4]

    def get_summery(self):
        return '{{"name": "{name}", "type": "{data_type}", "is_primary_key": "{is_nullable}", "comment": "{comment}", "default": "{default_value}"}}'.format(
            name=self.name,
            data_type=self.data_type,
            is_nullable=self.is_nullable,
            default_value=self.default_value,
            comment=self.comment,
        )


class MysqlIndexSummary(IndexSummary):
    """Get mysql index summary template."""

    def __init__(self, index):
        self.name = index[0]
        # self.summery = """index name:{name}, index bind columns:{bind_fields}"""
        self.summery_template = '{{"name": "{name}", "columns": {bind_fields}}}'
        self.bind_fields = index[1]

    def get_summery(self):
        return self.summery_template.format(
            name=self.name, bind_fields=self.bind_fields
        )


if __name__ == "__main__":
    summary = MysqlSummary("db_test")
    print(summary.get_summery())
