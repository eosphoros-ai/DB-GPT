from pilot.configs.config import Config
from pilot.summary.db_summary import DBSummary

CFG = Config()


class RdbmsSummary(DBSummary):
    """Get rdbms db table summary template.
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
        self.table_info_summaries = [
            self.get_table_summary(table_name) for table_name in tables
        ]

    def get_table_summary(self, table_name):
        """Get table summary for table.
        example:
            table_name(column1(column1 comment),column2(column2 comment),column3(column3 comment) and index keys, and table comment: {table_comment})
        """
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
        except Exception:
            comment = dict(text=None)
        if comment.get("text"):
            table_str += f", and table comment: {comment.get('text')}"
        return table_str

    def table_summaries(self):
        """Get table summaries."""
        return self.table_info_summaries
