import json

from pilot.configs.config import Config
from pilot.summary.db_summary import DBSummary, TableSummary, FieldSummary, IndexSummary

CFG = Config()


class RdbmsSummary(DBSummary):
    """Get db summary template.
    summary example:
    table_name(column1(column1 comment),column2(column2 comment),column3(column3 comment) and index keys, and table comment is {table_comment})
    """

    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.summary_template = "{table_name}({columns})"
        self.tables = {}
        self.tables_info = []
        self.vector_tables_info = []

        self.db = CFG.LOCAL_DB_MANAGE.get_connect(name)

        self.metadata = """user info :{users}, grant info:{grant}, charset:{charset}, collation:{collation}""".format(
            users=self.db.get_users(),
            grant=self.db.get_grants(),
            charset=self.db.get_charset(),
            collation=self.db.get_collation(),
        )
        tables = self.db.get_table_names()
        self.table_info_summaries = []
        for table_name in tables:
            table_profile = self.get_table_summary(table_name)
            self.table_info_summaries.append(table_profile)

    def get_table_summary(self, table_name):
        """Get table summary for table."""
        columns = []
        for column in self.db._inspector.get_columns(table_name):
            if column.get("comment"):
                columns.append((f"{column['name']} ({column.get('comment')})"))
            else:
                columns.append(f"{column['name']}")

        column_str = ", ".join(columns)
        index_keys = []
        for index_key in self.db._inspector.get_indexes(table_name):
            key_str = ", ".join(index_key["column_names"])
            index_keys.append(f"{index_key['name']}(`{key_str}`) ")
        table_str = self.summary_template.format(
            table_name=table_name, columns=column_str
        )
        if len(index_keys) > 0:
            index_key_str = ", ".join(index_keys)
            table_str += f", and index keys: {index_key_str}"
        try:
            comment = self.db._inspector.get_table_comment(table_name)
        except Exception as e:
            comment = dict(text=None)
        if comment.get("text"):
            table_str += f", and table comment: {comment.get('text')}"
        return table_str

    def get_table_comments(self):
        return self.table_comments

    def table_summaries(self):
        return self.table_info_summaries


class RdbmsTableSummary(TableSummary):
    """Get mysql table summary template."""

    def __init__(self, instance, dbname, name, comment_map):
        self.name = name
        self.dbname = dbname
        self.summary = """database name:{dbname}, table name:{name}, have columns info: {fields}, have indexes info: {indexes}"""
        self.json_summary_template = """{{"table_name": "{name}", "comment": "{comment}", "columns": "{fields}", "indexes": "{indexes}", "size_in_bytes": {size_in_bytes},  "rows": {rows}}}"""
        self.fields = []
        self.fields_info = []
        self.indexes = []
        self.indexes_info = []
        self.db = instance
        fields = self.db.get_fields(name)
        indexes = self.db.get_indexes(name)
        field_names = []
        for field in fields:
            field_summary = RdbmsFieldsSummary(field)
            self.fields.append(field_summary)
            self.fields_info.append(field_summary.get_summary())
            field_names.append(field[0])

        self.column_summary = """{name}({columns_info})""".format(
            name=name, columns_info=",".join(field_names)
        )

        for index in indexes:
            index_summary = RdbmsIndexSummary(index)
            self.indexes.append(index_summary)
            self.indexes_info.append(index_summary.get_summary())

        self.json_summary = self.json_summary_template.format(
            name=name,
            comment=comment_map[name],
            fields=self.fields_info,
            indexes=self.indexes_info,
            size_in_bytes=1000,
            rows=1000,
        )

    def get_columns(self):
        return self.column_summary

    def get_summary_json(self):
        return self.json_summary


class RdbmsFieldsSummary(FieldSummary):
    """Get mysql field summary template."""

    def __init__(self, field):
        self.name = field[0]
        # self.summary = """column name:{name}, column data type:{data_type}, is nullable:{is_nullable}, default value is:{default_value}, comment is:{comment} """
        # self.summary = """{"name": {name}, "type": {data_type}, "is_primary_key": {is_nullable}, "comment":{comment}, "default":{default_value}}"""
        self.data_type = field[1]
        self.default_value = field[2]
        self.is_nullable = field[3]
        self.comment = field[4]

    def get_summary(self):
        return '{{"name": "{name}", "type": "{data_type}", "is_primary_key": "{is_nullable}", "comment": "{comment}", "default": "{default_value}"}}'.format(
            name=self.name,
            data_type=self.data_type,
            is_nullable=self.is_nullable,
            default_value=self.default_value,
            comment=self.comment,
        )


class RdbmsIndexSummary(IndexSummary):
    """Get mysql index summary template."""

    def __init__(self, index):
        self.name = index[0]
        # self.summary = """index name:{name}, index bind columns:{bind_fields}"""
        self.summary_template = '{{"name": "{name}", "columns": {bind_fields}}}'
        self.bind_fields = index[1]

    def get_summary(self):
        return self.summary_template.format(
            name=self.name, bind_fields=self.bind_fields
        )
