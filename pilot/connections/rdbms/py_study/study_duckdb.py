import json
import os
import duckdb

default_db_path = os.path.join(os.getcwd(), "message")
duckdb_path = os.getenv("DB_DUCKDB_PATH", default_db_path + "/chat_history.db")

if __name__ == "__main__":
    if os.path.isfile("../../../message/chat_history.db"):
        cursor = duckdb.connect("../../../message/chat_history.db").cursor()
        # cursor.execute("SELECT * FROM chat_history limit 20")
        cursor.execute("SELECT * FROM chat_history  where conv_uid ='b54ae5fe-1624-11ee-a271-b26789cc3e58'")
        data = cursor.fetchall()
        print(data)
