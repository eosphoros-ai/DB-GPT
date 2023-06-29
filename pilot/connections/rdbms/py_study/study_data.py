from pilot.common.sql_database import Database
from pilot.configs.config import Config

CFG = Config()

if __name__ == "__main__":
    connect = CFG.local_db.get_session("gpt-user")
    datas = CFG.local_db.run(connect, "SELECT * FROM users; ")

    print(datas)