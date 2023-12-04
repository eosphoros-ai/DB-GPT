import duckdb
import pymysql

""" migrate duckdb to mysql"""

mysql_config = {
    "host": "127.0.0.1",
    "user": "root",
    "password": "your_password",
    "db": "dbgpt",
    "charset": "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
}

duckdb_files_to_tables = {
    "pilot/message/chat_history.db": "chat_history",
    "pilot/message/connect_config.db": "connect_config",
}

conn_mysql = pymysql.connect(**mysql_config)


def migrate_table(duckdb_file_path, source_table, destination_table, conn_mysql):
    conn_duckdb = duckdb.connect(duckdb_file_path)
    try:
        cursor = conn_duckdb.cursor()
        cursor.execute(f"SELECT * FROM {source_table}")
        column_names = [
            desc[0] for desc in cursor.description if desc[0].lower() != "id"
        ]
        select_columns = ", ".join(column_names)

        cursor.execute(f"SELECT {select_columns} FROM {source_table}")
        results = cursor.fetchall()

        with conn_mysql.cursor() as cursor_mysql:
            for row in results:
                placeholders = ", ".join(["%s"] * len(row))
                insert_query = f"INSERT INTO {destination_table} ({', '.join(column_names)}) VALUES ({placeholders})"
                cursor_mysql.execute(insert_query, row)
        conn_mysql.commit()
    finally:
        conn_duckdb.close()


try:
    for duckdb_file, table in duckdb_files_to_tables.items():
        print(f"Migrating table {table} from {duckdb_file}...")
        migrate_table(duckdb_file, table, table, conn_mysql)
        print(f"Table {table} migrated successfully.")
finally:
    conn_mysql.close()

print("Migration completed.")
