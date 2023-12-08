import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dbgpt._private.config import Config
from dbgpt.storage.schema import DBType
from dbgpt.datasource.rdbms.base import RDBMSDatabase

logger = logging.getLogger(__name__)
CFG = Config()


class BaseDao:
    def __init__(
        self, orm_base=None, database: str = None, create_not_exist_table: bool = False
    ) -> None:
        """BaseDAO, If the current database is a file database and create_not_exist_table=True, we will automatically create a table that does not exist"""
        self._orm_base = orm_base
        self._database = database
        self._create_not_exist_table = create_not_exist_table

        self._db_engine = None
        self._session = None
        self._connection = None

    @property
    def db_engine(self):
        if not self._db_engine:
            # lazy loading
            db_engine, connection = _get_db_engine(
                self._orm_base, self._database, self._create_not_exist_table
            )
            self._db_engine = db_engine
            self._connection = connection
        return self._db_engine

    @property
    def Session(self):
        if not self._session:
            self._session = sessionmaker(bind=self.db_engine)
        return self._session


def _get_db_engine(
    orm_base=None, database: str = None, create_not_exist_table: bool = False
):
    db_engine = None
    connection: RDBMSDatabase = None

    db_type = DBType.of_db_type(CFG.LOCAL_DB_TYPE)
    if db_type is None or db_type == DBType.Mysql:
        # default database
        db_engine = create_engine(
            f"mysql+pymysql://{CFG.LOCAL_DB_USER}:{CFG.LOCAL_DB_PASSWORD}@{CFG.LOCAL_DB_HOST}:{CFG.LOCAL_DB_PORT}/{database}",
            echo=True,
        )
    else:
        db_namager = CFG.LOCAL_DB_MANAGE
        if not db_namager:
            raise Exception(
                "LOCAL_DB_MANAGE is not initialized, please check the system configuration"
            )
        if db_type.is_file_db():
            db_path = CFG.LOCAL_DB_PATH
            if db_path is None or db_path == "":
                raise ValueError(
                    "You LOCAL_DB_TYPE is file db, but LOCAL_DB_PATH is not configured, please configure LOCAL_DB_PATH in you .env file"
                )
            _, database = db_namager._parse_file_db_info(db_type.value(), db_path)
            logger.info(
                f"Current DAO database is file database, db_type: {db_type.value()}, db_path: {db_path}, db_name: {database}"
            )
        logger.info(f"Get DAO database connection with database name {database}")
        connection: RDBMSDatabase = db_namager.get_connect(database)
        if not isinstance(connection, RDBMSDatabase):
            raise ValueError(
                "Currently only supports `RDBMSDatabase` database as the underlying database of BaseDao, please check your database configuration"
            )
        db_engine = connection._engine

        if db_type.is_file_db() and orm_base is not None and create_not_exist_table:
            logger.info("Current database is file database, create not exist table")
            orm_base.metadata.create_all(db_engine)

    return db_engine, connection
