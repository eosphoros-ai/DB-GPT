"""SQL-injection regression tests for ConnectConfigDao.

Locks the fix for f-string SQL in get_db_list/update_db_info, where request
parameters (db_name, user_id, comment, ...) were interpolated into SQL text
executed against the metadata database, allowing unauthenticated read/write
of arbitrary tables (passwords, API keys) via /api/v1/chat/db/*.

Locked behaviors:
1. get_db_list treats injection payloads as literal values: tautologies and
   UNION probes match no rows; the user_id filter cannot be bypassed.
2. update_db_info stores quotes/comments verbatim and only touches the
   targeted row — comment-injection cannot rewrite other records.
3. A failed write propagates instead of returning success.
"""

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.session import Session

from dbgpt.storage.metadata.db_manager import DatabaseManager
from dbgpt_serve.datasource.manages.connect_config_db import (
    ConnectConfigDao,
    ConnectConfigEntity,
)


@pytest.fixture()
def dao(tmp_path):
    dbm = DatabaseManager()
    dbm.init_db(f"sqlite:///{tmp_path}/meta.db")
    ConnectConfigEntity.__table__.create(dbm.engine)
    dao = ConnectConfigDao(db_manager=dbm)
    session = dao.get_raw_session()
    session.add_all(
        [
            ConnectConfigEntity(
                db_name="poc_target",
                db_type="mysql",
                db_host="10.0.0.9",
                db_port="3306",
                db_user="root",
                db_pwd="P0CSQ",
                comment="poc row",
                user_id="001",
            ),
            ConnectConfigEntity(
                db_name="Walmart_Sales",
                db_type="sqlite",
                comment="example",
                user_id="",
            ),
        ]
    )
    session.commit()
    session.close()
    return dao


def test_tautology_injection_matches_nothing(dao):
    assert dao.get_db_list(db_name="NOSUCH' OR '1'='1") == []
    assert len(dao.get_db_list()) == 2


def test_union_probe_is_a_literal_value(dao):
    payload = (
        "x' UNION SELECT 1,'t',name,'p','h','6','u','w',sql,'s','i','n',"
        "'13','14','15' FROM sqlite_master WHERE type='table' -- "
    )
    assert dao.get_db_list(db_name=payload) == []


def test_user_id_filter_cannot_be_bypassed(dao):
    rows = dao.get_db_list(user_id="001' OR '1'='1")
    assert {r["db_name"] for r in rows} == {"Walmart_Sales"}


def test_legit_lookup_still_works(dao):
    rows = dao.get_db_list(db_name="poc_target")
    assert len(rows) == 1
    assert rows[0]["db_pwd"] == "P0CSQ"


def test_comment_injection_only_updates_target_row(dao):
    payload = "PWN' where db_name='Walmart_Sales' -- "
    assert (
        dao.update_db_info(
            "poc_target", "mysql", "", "1.1.1.1", 3306, "root", "INJ", payload
        )
        is True
    )
    target = dao.get_db_list(db_name="poc_target")[0]
    assert target["comment"] == payload
    assert target["db_host"] == "1.1.1.1"
    other = dao.get_db_list(db_name="Walmart_Sales")[0]
    assert other["db_type"] == "sqlite"
    assert other["comment"] == "example"


def test_write_failure_propagates(dao, monkeypatch):
    real_execute = Session.execute

    def flaky_execute(self, stmt, *args, **kwargs):
        if "UPDATE" in str(stmt):
            raise OperationalError("boom", {}, None)
        return real_execute(self, stmt, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", flaky_execute)
    with pytest.raises(OperationalError):
        dao.update_db_info("poc_target", "mysql", "", "2.2.2.2", 3306, "u", "p", "c")
    assert dao.get_db_list(db_name="poc_target")[0]["db_host"] == "10.0.0.9"
