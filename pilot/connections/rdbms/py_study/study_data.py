import json
from pilot.common.sql_database import Database
from pilot.configs.config import Config

CFG = Config()

if __name__ == "__main__":
    # connect = CFG.local_db.get_session("gpt-user")
    # datas = CFG.local_db.run(connect, "SELECT * FROM users; ")

    # print(datas)

    # str = """{ "thoughts": "thought text", "sql": "SELECT COUNT(DISTINCT user_id) FROM transactions_order WHERE user_id IN (SELECT DISTINCT user_id FROM users WHERE country='China') AND create_time BETWEEN 20230101 AND 20230131" ,}"""
    #
    # print(str.find("["))

    test =["t1", "t2", "t3", "tx"]
    print(str(test[1:]))


