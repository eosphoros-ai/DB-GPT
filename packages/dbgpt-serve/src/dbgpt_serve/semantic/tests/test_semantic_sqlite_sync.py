"""Exercise SQLAlchemy primary-key flags through a real SQLite connector."""

import sqlite3

from dbgpt.storage.metadata import db
from dbgpt_ext.datasource.rdbms.conn_sqlite import SQLiteConnector
from dbgpt_serve.semantic.models import SemColumnDao, SemTableDao
from dbgpt_serve.semantic.sync import SemanticSyncService


def test_sqlite_sync_preserves_primary_keys_on_create_and_resync(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as conn:
        conn.execute(
            "CREATE TABLE order_items ("
            "order_id INTEGER, item_id INTEGER, amount INTEGER, "
            "PRIMARY KEY (order_id, item_id))"
        )
    db.init_db(f"sqlite:///{tmp_path / 'meta.db'}")
    db.create_all()
    connector = SQLiteConnector.from_file_path(str(source))
    try:
        sync = SemanticSyncService()
        for _ in range(2):
            report = sync.sync("sqlite_pk_case", connector)
            table = SemTableDao().list_by_ds(report.ds_id, status="active")[0]
            columns = SemColumnDao().list_by_table(report.ds_id, table.id)
            assert {c.column_name: c.is_pk for c in columns} == {
                "order_id": True,
                "item_id": True,
                "amount": False,
            }
    finally:
        connector._engine.dispose()
