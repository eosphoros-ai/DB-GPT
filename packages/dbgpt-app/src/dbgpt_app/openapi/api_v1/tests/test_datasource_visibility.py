from types import SimpleNamespace

import pytest

from dbgpt_app.openapi.api_v1.datasource_visibility import (
    is_hidden_datasource,
    resolves_to_hidden_datasource,
)

_ROWS = [
    {"db_name": "dbgpt", "db_type": "mysql"},
    {"db_name": "DBGPT ", "db_type": "mysql"},
    {"db_name": "public", "db_type": "postgresql"},
    {"db_name": "walmart_sales", "db_type": "sqlite"},
    {"db_name": "dbgpt_demo", "db_type": "mysql"},
]


@pytest.mark.parametrize(
    "name", ["dbgpt", "DBGPT", " dbgpt ", "auth", "Test", "public\t"]
)
def test_reserved_names_are_hidden(name):
    assert is_hidden_datasource(name)


@pytest.mark.parametrize("name", ["walmart_sales", "dbgpt_demo", "testing", "", None])
def test_other_names_are_not_hidden(name):
    assert not is_hidden_datasource(name)


@pytest.fixture
def db_rows(monkeypatch):
    from dbgpt_app.openapi.api_v1 import api_v1

    manager = SimpleNamespace(get_db_list=lambda db_name=None, user_id=None: _ROWS)
    monkeypatch.setattr(api_v1, "CFG", SimpleNamespace(local_db_manager=manager))
    return api_v1


def test_chat_mode_params_list_skips_hidden_datasources(db_rows):
    params = db_rows.get_db_list()
    assert [p["param"] for p in params] == ["walmart_sales", "dbgpt_demo"]


@pytest.mark.asyncio
async def test_db_connect_list_skips_hidden_datasources(db_rows):
    result = await db_rows.db_connect_list(
        db_name=None, user_info=SimpleNamespace(user_id="alice")
    )
    assert [d["db_name"] for d in result.data] == ["walmart_sales", "dbgpt_demo"]


def _manager_storing(stored_name):
    def _lookup(name):
        return None if stored_name is None else SimpleNamespace(db_name=stored_name)

    return SimpleNamespace(storage=SimpleNamespace(get_by_names=_lookup))


def test_name_resolving_to_hidden_row_is_hidden():
    assert resolves_to_hidden_datasource(_manager_storing("dbgpt"), "dbĝpt")
    assert resolves_to_hidden_datasource(_manager_storing(None), "DBGPT")


def test_name_resolving_to_user_row_is_not_hidden():
    assert not resolves_to_hidden_datasource(_manager_storing("walmart"), "walmart")
    assert not resolves_to_hidden_datasource(_manager_storing(None), "missing")
    assert not resolves_to_hidden_datasource(_manager_storing("dbgpt"), "  ")
