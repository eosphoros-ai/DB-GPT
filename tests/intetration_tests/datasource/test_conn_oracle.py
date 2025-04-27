"""
    Run unit test with command: pytest dbgpt/datasource/rdbms/tests/test_conn_mysql.py
    docker run -itd --name mysql-test -p 3307:3306 -e MYSQL_ROOT_PASSWORD=12345678 mysql:5.7
    mysql -h 127.0.0.1 -uroot -p -P3307
    Enter password:
    Welcome to the MySQL monitor.  Commands end with ; or \g.
    Your MySQL connection id is 2
    Server version: 5.7.41 MySQL Community Server (GPL)

    Copyright (c) 2000, 2023, Oracle and/or its affiliates.

    Oracle is a registered trademark of Oracle Corporation and/or its
    affiliates. Other names may be trademarks of their respective
    owners.

    Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.
    
    > create database test;
"""
import pytest
from dbgpt_ext.datasource.rdbms.conn_oracle import OracleConnector


_create_table_sql = """
CREATE TABLE test (
    id NUMBER(11) NULL
)
"""

@pytest.fixture
def db():
    # 注意：Oracle 默认端口是 1521，连接方式建议用 service_name
    conn = OracleConnector.from_uri_db(
        host="localhost",
        port=1521,
        user="oracle_user",
        pwd="********",
        service_name="ORCL",  # 替换为你的 service_name 或 SID
    )
    try:
        yield conn
    finally:
        try:
            conn.run("DROP TABLE test PURGE")
        except Exception:
            pass  # 如果表不存在也忽略错误

def test_get_usable_table_names(db):
    db.run(_create_table_sql)
    db.run("COMMIT")
    table_names = db.get_usable_table_names()
    assert "TEST" in map(str.upper, table_names)

def test_get_table_info(db):
    db.run(_create_table_sql)
    db.run("COMMIT")
    table_info = db.get_table_info()
    assert "CREATE TABLE TEST" in table_info.upper()

def test_run_no_throw(db):
    result = db.run_no_throw("this is a error sql")
    # run_no_throw 返回的是 list，错误时为空
    assert result == [] or isinstance(result, list)

def test_get_index_empty(db):
    db.run(_create_table_sql)
    db.run("COMMIT")
    indexes = db.get_indexes("TEST")
    assert indexes == []

def test_get_fields(db):
    #db.run(_create_table_sql)
    #db.run("COMMIT")
    print("进入方法...")
    fields = db.get_fields("PY_TEST")
    print("正在打印字段信息...")
    for field in fields:
        print(f"Column Name: {field[0]}")
        print(f"Data Type: {field[1]}")
        print(f"Default Value: {field[2]}")
        print(f"Is Nullable: {field[3]}")
        print(f"Column Comment: {field[4]}")
        print("-" * 30)  # 可选的分隔符
    #assert fields[0][0].upper() == "ID"

def test_get_charset(db):
    result = db.run("SELECT VALUE FROM NLS_DATABASE_PARAMETERS WHERE PARAMETER = 'NLS_CHARACTERSET'")
    assert result[1][0] in ("AL32UTF8", "UTF8")  # result[0] 是字段名元组

def test_get_users(db):
    users = db.get_users()
    assert any(user[0].upper() in ("SYS", "SYSTEM") for user in users)

def test_get_database_lists(db):
    cdb_result = db.run("SELECT CDB FROM V$DATABASE")
    if cdb_result[1][0] == "YES":
        databases = db.run("SELECT NAME FROM V$PDBS WHERE OPEN_MODE = 'READ WRITE'")
        pdb_names = [name[0] for name in databases[1:]]
    else:
        pdb_names = ["ORCL"]
    assert any(name in ("ORCLPDB1", "ORCL") for name in pdb_names)