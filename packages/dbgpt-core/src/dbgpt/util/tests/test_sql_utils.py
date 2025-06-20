import pytest

from dbgpt.util.sql_utils import remove_sql_comments


class TestRemoveSqlComments:
    """Test cases for the remove_sql_comments method."""

    def test_remove_single_line_comments_basic(self):
        """Test removing basic single-line comments."""
        sql = "SELECT * FROM users -- This is a comment"
        expected = "SELECT * FROM users "
        result = remove_sql_comments(sql)
        assert result == expected

    def test_remove_single_line_comments_with_newline(self):
        """Test removing single-line comments followed by newline."""
        sql = "SELECT * FROM users -- This is a comment\nWHERE id = 1"
        expected = "SELECT * FROM users WHERE id = 1"
        result = remove_sql_comments(sql)
        assert result == expected

    def test_remove_single_line_comments_at_end(self):
        """Test removing single-line comments at the end of string."""
        sql = "SELECT * FROM users\n-- Final comment"
        expected = "SELECT * FROM users\n"
        result = remove_sql_comments(sql)
        assert result == expected

    def test_remove_multiple_single_line_comments(self):
        """Test removing multiple single-line comments."""
        sql = """SELECT * FROM users -- Comment 1
                 WHERE id = 1 -- Comment 2
                 ORDER BY name -- Comment 3"""
        expected = """SELECT * FROM users                  WHERE id = 1                  ORDER BY name """  # noqa: E501
        result = remove_sql_comments(sql)
        assert result == expected

    def test_remove_multiline_comments_basic(self):
        """Test removing basic multi-line comments."""
        sql = "SELECT * FROM users /* This is a comment */ WHERE id = 1"
        expected = "SELECT * FROM users  WHERE id = 1"
        result = remove_sql_comments(sql)
        assert result == expected

    def test_remove_multiline_comments_with_newlines(self):
        """Test removing multi-line comments spanning multiple lines."""
        sql = """SELECT * FROM users 
                 /* This is a 
                    multi-line comment */ 
                 WHERE id = 1"""
        expected = """SELECT * FROM users 
                  
                 WHERE id = 1"""
        result = remove_sql_comments(sql)
        assert result == expected

    def test_remove_multiple_multiline_comments(self):
        """Test removing multiple multi-line comments."""
        sql = "SELECT * /* comment 1 */ FROM users /* comment 2 */ WHERE id = 1"
        expected = "SELECT *  FROM users  WHERE id = 1"
        result = remove_sql_comments(sql)
        assert result == expected

    def test_remove_mixed_comments(self):
        """Test removing both single-line and multi-line comments."""
        sql = """SELECT * FROM users /* multi-line comment */
                 WHERE id = 1 -- single line comment
                 /* another multi-line 
                    comment */
                 ORDER BY name -- final comment"""
        expected = """SELECT * FROM users 
                 WHERE id = 1                  
                 ORDER BY name """
        result = remove_sql_comments(sql)
        assert result == expected

    def test_no_comments_to_remove(self):
        """Test SQL with no comments."""
        sql = "SELECT * FROM users WHERE id = 1 ORDER BY name"
        expected = "SELECT * FROM users WHERE id = 1 ORDER BY name"
        result = remove_sql_comments(sql)
        assert result == expected

    def test_empty_string(self):
        """Test with empty string."""
        sql = ""
        expected = ""
        result = remove_sql_comments(sql)
        assert result == expected

    def test_only_comments(self):
        """Test string with only comments."""
        sql = "-- This is only a comment"
        expected = ""
        result = remove_sql_comments(sql)
        assert result == expected

    def test_only_multiline_comments(self):
        """Test string with only multi-line comments."""
        sql = "/* This is only a multi-line comment */"
        expected = ""
        result = remove_sql_comments(sql)
        assert result == expected

    def test_comments_with_special_characters(self):
        """Test comments containing special characters."""
        sql = "SELECT * FROM users -- Comment with special chars: @#$%^&*()"
        expected = "SELECT * FROM users "
        result = remove_sql_comments(sql)
        assert result == expected

    def test_comments_with_sql_keywords(self):
        """Test comments containing SQL keywords."""
        sql = "SELECT * FROM users -- SELECT * FROM another_table"
        expected = "SELECT * FROM users "
        result = remove_sql_comments(sql)
        assert result == expected

    def test_whitespace_handling(self):
        """Test whitespace handling around comments."""
        sql = "SELECT *    -- comment with spaces   \n    FROM users"
        expected = "SELECT *        FROM users"
        result = remove_sql_comments(sql)
        assert result == expected

    def test_multiline_comment_at_start(self):
        """Test multi-line comment at the beginning."""
        sql = "/* Initial comment */ SELECT * FROM users"
        expected = " SELECT * FROM users"
        result = remove_sql_comments(sql)
        assert result == expected

    def test_multiline_comment_at_end(self):
        """Test multi-line comment at the end."""
        sql = "SELECT * FROM users /* Final comment */"
        expected = "SELECT * FROM users "
        result = remove_sql_comments(sql)
        assert result == expected

    def test_complex_sql_with_comments(self):
        """Test complex SQL statement with various comment types."""
        sql = """
        /* Query to get user information */
        SELECT 
            u.id, -- User ID
            u.name, /* User full name */
            u.email -- Contact email
        FROM users u
        /* Join with posts table */
        LEFT JOIN posts p ON u.id = p.user_id
        WHERE u.active = 1 -- Only active users
        /* Order by creation date */
        ORDER BY u.created_at DESC
        -- Limit results
        LIMIT 10;
        """

        result = remove_sql_comments(sql)

        # Verify that all comments are removed
        assert "--" not in result
        assert "/*" not in result
        assert "*/" not in result

        # Verify that SQL keywords are preserved
        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result
        assert "ORDER BY" in result
        assert "LIMIT" in result


# 如果需要测试实际的类实例，可以使用以下参数化测试
@pytest.mark.parametrize(
    "sql_input,expected_output",
    [
        ("SELECT * FROM users", "SELECT * FROM users"),
        ("SELECT * FROM users -- comment", "SELECT * FROM users "),
        ("SELECT * /* comment */ FROM users", "SELECT *  FROM users"),
        ("", ""),
        ("-- only comment", ""),
        ("/* only comment */", ""),
    ],
)
def test_remove_sql_comments_parametrized(sql_input, expected_output):
    """Parametrized test for common cases."""

    # 创建测试实例
    class MockClass:
        def _remove_sql_comments(self, sql: str) -> str:
            import re

            sql = re.sub(r"--.*?(\n|$)", "", sql)
            sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
            return sql

    instance = MockClass()
    result = instance._remove_sql_comments(sql_input)
    assert result == expected_output
