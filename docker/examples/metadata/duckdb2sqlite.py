import duckdb
import sqlite3

""" migrate duckdb to sqlite"""

duckdb_files_to_tables = {
    "pilot/message/chat_history.db": "chat_history",
    "pilot/message/connect_config.db": "connect_config",
}

sqlite_db_path = "pilot/meta_data/dbgpt.db"

conn_sqlite = sqlite3.connect(sqlite_db_path)


def migrate_table(duckdb_file_path, source_table, destination_table, conn_sqlite):
    conn_duckdb = duckdb.connect(duckdb_file_path)
    try:
        cursor_duckdb = conn_duckdb.cursor()
        cursor_duckdb.execute(f"SELECT * FROM {source_table}")
        column_names = [
            desc[0] for desc in cursor_duckdb.description if desc[0].lower() != "id"
        ]
        select_columns = ", ".join(column_names)

        cursor_duckdb.execute(f"SELECT {select_columns} FROM {source_table}")
        results = cursor_duckdb.fetchall()

        cursor_sqlite = conn_sqlite.cursor()
        for row in results:
            placeholders = ", ".join(["?"] * len(row))
            insert_query = f"INSERT INTO {destination_table} ({', '.join(column_names)}) VALUES ({placeholders})"
            cursor_sqlite.execute(insert_query, row)
        conn_sqlite.commit()
        cursor_sqlite.close()
    finally:
        conn_duckdb.close()


try:
    for duckdb_file, table in duckdb_files_to_tables.items():
        print(f"Migrating table {table} from {duckdb_file} to SQLite...")
        migrate_table(duckdb_file, table, table, conn_sqlite)
        print(f"Table {table} migrated to SQLite successfully.")
finally:
    conn_sqlite.close()

print("Migration to SQLite completed.")
