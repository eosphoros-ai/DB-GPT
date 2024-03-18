"""DB Model for connect_config."""

import logging
from typing import Optional

from sqlalchemy import Column, Index, Integer, String, Text, UniqueConstraint, text

from dbgpt.storage.metadata import BaseDao, Model

logger = logging.getLogger(__name__)


class ConnectConfigEntity(Model):
    """DB connector config entity."""

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
    )


class ConnectConfigDao(BaseDao):
    """DB connector config dao."""

    def get_by_names(self, db_name: str) -> Optional[ConnectConfigEntity]:
        """Get db connect info by name."""
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
        """Add db connect info.

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
                    db_name, db_type, db_path, db_host, db_port, db_user, db_pwd,
                    comment) VALUES (:db_name, :db_type, :db_path, :db_host, :db_port
                    , :db_user, :db_pwd, :comment
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
            logger.warning("add db connect info error！" + str(e))

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
        """Update db connect info."""
        old_db_conf = self.get_db_config(db_name)
        if old_db_conf:
            try:
                session = self.get_raw_session()
                if not db_path:
                    update_statement = text(
                        f"UPDATE connect_config set db_type='{db_type}', "
                        f"db_host='{db_host}', db_port={db_port}, db_user='{db_user}', "
                        f"db_pwd='{db_pwd}', comment='{comment}' where "
                        f"db_name='{db_name}'"
                    )
                else:
                    update_statement = text(
                        f"UPDATE connect_config set db_type='{db_type}', "
                        f"db_path='{db_path}', comment='{comment}' where "
                        f"db_name='{db_name}'"
                    )
                session.execute(update_statement)
                session.commit()
                session.close()
            except Exception as e:
                logger.warning("edit db connect info error！" + str(e))
            return True
        raise ValueError(f"{db_name} not have config info!")

    def add_file_db(self, db_name, db_type, db_path: str, comment: str = ""):
        """Add file db connect info."""
        try:
            session = self.get_raw_session()
            insert_statement = text(
                """
                INSERT INTO connect_config(
                    db_name, db_type, db_path, db_host, db_port, db_user, db_pwd,
                    comment) VALUES (
                    :db_name, :db_type, :db_path, :db_host, :db_port, :db_user, :db_pwd
                    , :comment
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
            logger.warning("add db connect info error！" + str(e))

    def get_db_config(self, db_name):
        """Return db connect info by name."""
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

        logger.info(f"Result: {result}")
        fields = [field[0] for field in result.cursor.description]
        row_dict = {}
        row_1 = list(result.cursor.fetchall()[0])
        for i, field in enumerate(fields):
            row_dict[field] = row_1[i]
        return row_dict

    def get_db_list(self):
        """Get db list."""
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
        """Delete db connect info."""
        session = self.get_raw_session()
        delete_statement = text("""DELETE FROM connect_config where db_name=:db_name""")
        params = {"db_name": db_name}
        session.execute(delete_statement, params)
        session.commit()
        session.close()
        return True
