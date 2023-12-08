import re
import sqlparse


def add_quotes(sql, column_names=[]):
    parsed = sqlparse.parse(sql)
    for stmt in parsed:
        for token in stmt.tokens:
            deep_quotes(token, column_names)
    return str(parsed[0])


def deep_quotes(token, column_names=[]):
    if hasattr(token, "tokens"):
        for token_child in token.tokens:
            deep_quotes(token_child, column_names)
    else:
        if token.ttype == sqlparse.tokens.Name:
            if len(column_names) > 0:
                if token.value in column_names:
                    token.value = f'"{token.value}"'
            else:
                token.value = f'"{token.value}"'
