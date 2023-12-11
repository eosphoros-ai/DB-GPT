from dbgpt._private.pydantic import BaseModel


class DBConfig(BaseModel):
    db_type: str
    db_name: str
    file_path: str = ""
    db_host: str = ""
    db_port: int = 0
    db_user: str = ""
    db_pwd: str = ""
    comment: str = ""


class DbTypeInfo(BaseModel):
    db_type: str
    is_file_db: bool = False
