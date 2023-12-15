from sqlalchemy import Column, Integer, String, Index, Text, text
from sqlalchemy import UniqueConstraint

from dbgpt.storage.metadata import BaseDao, Model


class ConnectConfigEntity(Model):
    """db connect config entity"""

    __tablename__ = "connect_config"
    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="autoincrement id"
    )

    db_type = Column(String(255), nullable=False, comment="db type")
    db_name = Column(String(255), nullable=False, comment="db name")
    db_path = Column(String(255), nullable=True, comment="file db path")
    db_host = Column(String(255), nullable=True, comment="db connect host(not file db)")
    db_port = Column(String(255), nullable=True, comment="db connect port(not file db)")
    db_user = Column(String(255), nullable=True, comment="db user")
    db_pwd = Column(String(255), nullable=True, comment="db password")
    comment = Column(Text, nullable=True, comment="db comment")
    sys_code = Column(String(128), index=True, nullable=True, comment="System code")

    __table_args__ = (
        UniqueConstraint("db_name", name="uk_db"),
        Index("idx_q_db_type", "db_type"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )


class ConnectConfigDao(BaseDao[ConnectConfigEntity]):
    """db connect config dao"""

    def update(self, entity: ConnectConfigEntity):
        """update db connect info"""
        session = self.get_raw_session()
        try:
            updated = session.merge(entity)
            session.commit()
            return updated.id
        finally:
            session.close()

    def delete(self, db_name: int):
        """ "delete db connect info"""
        session = self.get_raw_session()
        if db_name is None:
            raise Exception("db_name is None")

        db_connect = session.query(ConnectConfigEntity)
        db_connect = db_connect.filter(ConnectConfigEntity.db_name == db_name)
        db_connect.delete()
        session.commit()
        session.close()

    def get_by_names(self, db_name: str) -> ConnectConfigEntity:
        """get db connect info by name"""
        session = self.get_raw_session()
        db_connect = session.query(ConnectConfigEntity)
        db_connect = db_connect.filter(ConnectConfigEntity.db_name == db_name)
        result = db_connect.first()
        session.close()
        return result

    def add_url_db(
        self,
        db_name,
        db_type,
        db_host: str,
        db_port: int,
        db_user: str,
        db_pwd: str,
        comment: str = "",
    ):
        """
        add db connect info
        Args:
            db_name: db name
            db_type: db type
            db_host: db host
            db_port: db port
            db_user: db user
            db_pwd: db password
            comment: comment
        """
        try:
            session = self.get_raw_session()

            from sqlalchemy import text

            insert_statement = text(
                """
                INSERT INTO connect_config (
                    db_name, db_type, db_path, db_host, db_port, db_user, db_pwd, comment
                ) VALUES (
                    :db_name, :db_type, :db_path, :db_host, :db_port, :db_user, :db_pwd, :comment
                )
            """
            )

            params = {
                "db_name": db_name,
                "db_type": db_type,
                "db_path": "",
                "db_host": db_host,
                "db_port": db_port,
                "db_user": db_user,
                "db_pwd": db_pwd,
                "comment": comment,
            }
            session.execute(insert_statement, params)
            session.commit()
            session.close()
        except Exception as e:
            print("add db connect info error！" + str(e))

    def update_db_info(
        self,
        db_name,
        db_type,
        db_path: str = "",
        db_host: str = "",
        db_port: int = 0,
        db_user: str = "",
        db_pwd: str = "",
        comment: str = "",
    ):
        """update db connect info"""
        old_db_conf = self.get_db_config(db_name)
        if old_db_conf:
            try:
                session = self.get_raw_session()
                if not db_path:
                    update_statement = text(
                        f"UPDATE connect_config set db_type='{db_type}', db_host='{db_host}', db_port={db_port}, db_user='{db_user}', db_pwd='{db_pwd}', comment='{comment}' where db_name='{db_name}'"
                    )
                else:
                    update_statement = text(
                        f"UPDATE connect_config set db_type='{db_type}', db_path='{db_path}', comment='{comment}' where db_name='{db_name}'"
                    )
                session.execute(update_statement)
                session.commit()
                session.close()
            except Exception as e:
                print("edit db connect info error！" + str(e))
            return True
        raise ValueError(f"{db_name} not have config info!")

    def add_file_db(self, db_name, db_type, db_path: str, comment: str = ""):
        """add file db connect info"""
        try:
            session = self.get_raw_session()
            insert_statement = text(
                """
                INSERT INTO connect_config(
                    db_name, db_type, db_path, db_host, db_port, db_user, db_pwd, comment
                ) VALUES (
                    :db_name, :db_type, :db_path, :db_host, :db_port, :db_user, :db_pwd, :comment
                )
            """
            )
            params = {
                "db_name": db_name,
                "db_type": db_type,
                "db_path": db_path,
                "db_host": "",
                "db_port": 0,
                "db_user": "",
                "db_pwd": "",
                "comment": comment,
            }

            session.execute(insert_statement, params)

            session.commit()
            session.close()
        except Exception as e:
            print("add db connect info error！" + str(e))

    def get_db_config(self, db_name):
        """get db config by name"""
        session = self.get_raw_session()
        if db_name:
            select_statement = text(
                """
                SELECT 
                    *
                FROM 
                    connect_config 
                WHERE 
                    db_name = :db_name
            """
            )
            params = {"db_name": db_name}
            result = session.execute(select_statement, params)

        else:
            raise ValueError("Cannot get database by name" + db_name)

        fields = [field[0] for field in result.cursor.description]
        row_dict = {}
        row_1 = list(result.cursor.fetchall()[0])
        for i, field in enumerate(fields):
            row_dict[field] = row_1[i]
        return row_dict

    def get_db_list(self):
        """get db list"""
        session = self.get_raw_session()
        result = session.execute(text("SELECT *  FROM connect_config"))

        fields = [field[0] for field in result.cursor.description]
        data = []
        for row in result.cursor.fetchall():
            row_dict = {}
            for i, field in enumerate(fields):
                row_dict[field] = row[i]
            data.append(row_dict)
        return data

    def delete_db(self, db_name):
        """delete db connect info"""
        session = self.get_raw_session()
        delete_statement = text("""DELETE FROM connect_config where db_name=:db_name""")
        params = {"db_name": db_name}
        session.execute(delete_statement, params)
        session.commit()
        session.close()
        return True
