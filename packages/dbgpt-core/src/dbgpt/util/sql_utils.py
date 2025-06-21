import re


def remove_sql_comments(sql: str) -> str:
    """Remove SQL comments from the given SQL string."""

    # Remove single-line comments (--) and multi-line comments (/* ... */)
    sql = re.sub(r"--.*?(\n|$)", "", sql)
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql
