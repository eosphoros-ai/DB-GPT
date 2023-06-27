import json
import os
import duckdb

default_db_path = os.path.join(os.getcwd(), "message")
duckdb_path = os.getenv("DB_DUCKDB_PATH", default_db_path + "/chat_history.db")

if __name__ == "__main__":
    if os.path.isfile(duckdb_path):
        cursor = duckdb.connect(duckdb_path).cursor()
        cursor.execute("SELECT * FROM chat_history limit 20")
        data = cursor.fetchall()
        print(data)
