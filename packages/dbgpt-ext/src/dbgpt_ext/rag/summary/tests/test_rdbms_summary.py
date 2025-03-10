import unittest
from unittest.mock import Mock

from ...summary.rdbms_db_summary import RdbmsSummary


class MockRDBMSConnector(object):
    def get_users(self):
        return "user1, user2"

    def get_grants(self):
        return "grant1, grant2"

    def get_charset(self):
        return "utf8"

    def get_collation(self):
        return "utf8_general_ci"

    def get_table_names(self):
        return ["table1", "table2"]

    def get_columns(self, table_name):
        if table_name == "table1":
            return [{"name": "column1", "comment": "first column"}, {"name": "column2"}]
        return [{"name": "column1"}]

    def get_indexes(self, table_name):
        return [{"name": "index1", "column_names": ["column1"]}]

    def get_table_comment(self, table_name):
        return {"text": f"{table_name} comment"}


class TestRdbmsSummary(unittest.TestCase):
    def setUp(self):
        self.mock_local_db_manage = Mock()
        self.mock_local_db_manage.get_connector.return_value = MockRDBMSConnector()

    def test_rdbms_summary_initialization(self):
        rdbms_summary = RdbmsSummary(
            name="test_db", type="test_type", manager=self.mock_local_db_manage
        )
        self.assertEqual(rdbms_summary.name, "test_db")
        self.assertEqual(rdbms_summary.type, "test_type")
        self.assertTrue("user info :user1, user2" in rdbms_summary.metadata)
        self.assertTrue("grant info:grant1, grant2" in rdbms_summary.metadata)
        self.assertTrue("charset:utf8" in rdbms_summary.metadata)
        self.assertTrue("collation:utf8_general_ci" in rdbms_summary.metadata)

    def test_table_summaries(self):
        rdbms_summary = RdbmsSummary(
            name="test_db", type="test_type", manager=self.mock_local_db_manage
        )
        summaries = rdbms_summary.table_summaries()
        self.assertTrue(
            "table1(column1 (first column), column2), and index keys: index1(`column1`)"
            " , and table comment: table1 comment" in summaries
        )
        self.assertTrue(
            "table2(column1), and index keys: index1(`column1`) , and table comment: "
            "table2 comment" in summaries
        )


if __name__ == "__main__":
    unittest.main()
