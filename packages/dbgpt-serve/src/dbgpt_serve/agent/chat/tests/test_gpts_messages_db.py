"""Tests for database-specific GPT message column types."""

from sqlalchemy.dialects import mysql, postgresql, sqlite

from dbgpt_serve.agent.db.gpts_messages_db import GptsMessagesEntity


def test_large_message_columns_use_longtext_on_mysql():
    for column_name in ("content", "action_report"):
        column_type = GptsMessagesEntity.__table__.c[column_name].type

        assert column_type.dialect_impl(mysql.dialect()).compile() == "LONGTEXT"


def test_large_message_columns_remain_portable_text():
    content_type = GptsMessagesEntity.__table__.c.content.type

    assert content_type.dialect_impl(sqlite.dialect()).compile() == "TEXT"
    assert content_type.dialect_impl(postgresql.dialect()).compile() == "TEXT"
