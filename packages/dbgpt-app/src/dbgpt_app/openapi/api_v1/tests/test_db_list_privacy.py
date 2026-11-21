"""Regression tests ensuring /v1/chat/db/list never exposes plaintext db_pwd."""

from types import SimpleNamespace

import pytest

from dbgpt.storage.metadata.db_manager import DatabaseManager
from dbgpt_serve.datasource.manages.connect_config_db import (
    ConnectConfigDao,
    ConnectConfigEntity,
)
from dbgpt_serve.utils.auth import UserRequest


@pytest.mark.asyncio
async def test_db_connect_list_strips_db_pwd(monkeypatch):
    from dbgpt_app.openapi.api_v1 import api_v1

    raw_rows = [
        {
            "db_name": "sales_mysql",
            "db_type": "mysql",
            "db_host": "10.0.0.5",
            "db_port": 3306,
            "db_user": "readonly",
            "db_pwd": "super-secret-password",
            "comment": "Sales analytics",
        },
        {
            "db_name": "auth",
            "db_type": "sqlite",
            "db_pwd": "internal-secret",
        },
    ]

    class FakeDbManager:
        def get_db_list(self, db_name=None, user_id=None):
            return raw_rows

    monkeypatch.setattr(
        api_v1, "CFG", SimpleNamespace(local_db_manager=FakeDbManager())
    )

    resp = await api_v1.db_connect_list(
        db_name=None, user_info=UserRequest(user_id="alice")
    )
    assert resp.success is True
    assert len(resp.data) == 1
    row = resp.data[0]
    assert row["db_name"] == "sales_mysql"
    assert row["db_host"] == "10.0.0.5"
    assert row["db_user"] == "readonly"
    assert "db_pwd" not in row
    # Underlying row returned by manager must not be mutated in place
    assert raw_rows[0]["db_pwd"] == "super-secret-password"


def test_update_db_info_preserves_password_when_omitted(tmp_path):
    dbm = DatabaseManager()
    dbm.init_db(f"sqlite:///{tmp_path}/meta.db")
    ConnectConfigEntity.__table__.create(dbm.engine)
    dao = ConnectConfigDao(db_manager=dbm)
    dao.add_url_db(
        db_name="prod_db",
        db_type="mysql",
        db_host="10.0.0.9",
        db_port=3306,
        db_user="app",
        db_pwd="existing-secret",
        comment="initial",
        user_id="alice",
    )

    # Editing comment with empty db_pwd (e.g. from UI after redaction) keeps password
    assert (
        dao.update_db_info(
            db_name="prod_db",
            db_type="mysql",
            db_path="",
            db_host="10.0.0.9",
            db_port=3306,
            db_user="app",
            db_pwd="",
            comment="updated comment",
        )
        is True
    )
    updated = dao.get_db_config("prod_db")
    assert updated["comment"] == "updated comment"
    assert updated["db_pwd"] == "existing-secret"

    # Explicit non-empty db_pwd updates the password
    assert (
        dao.update_db_info(
            db_name="prod_db",
            db_type="mysql",
            db_path="",
            db_host="10.0.0.9",
            db_port=3306,
            db_user="app",
            db_pwd="rotated-secret",
            comment="rotated",
        )
        is True
    )
    rotated = dao.get_db_config("prod_db")
    assert rotated["db_pwd"] == "rotated-secret"
