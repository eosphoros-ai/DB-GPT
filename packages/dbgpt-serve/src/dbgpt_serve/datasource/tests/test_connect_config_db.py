"""Tests for the editable display_name alias on datasource configs (#2987)."""

import pytest

from dbgpt.storage.metadata import db

from ..manages.connect_config_db import ConnectConfigDao, ConnectConfigEntity


@pytest.fixture(autouse=True)
def setup_and_teardown():
    db.init_db("sqlite:///:memory:")
    db.create_all()

    yield


@pytest.fixture
def dao():
    return ConnectConfigDao()


def test_table_has_display_name_column():
    table = ConnectConfigEntity.__table__
    assert "display_name" in table.columns


def test_create_and_read_alias(dao):
    entity = dao.create(
        {
            "db_type": "mysql",
            "db_name": "prod_orders",
            "display_name": "生产订单库(10.0.0.1)",
            "db_host": "10.0.0.1",
            "db_port": 3306,
        }
    )
    assert entity.display_name == "生产订单库(10.0.0.1)"

    stored = dao.get_by_names("prod_orders")
    assert stored is not None
    assert stored.display_name == "生产订单库(10.0.0.1)"


def test_alias_optional_defaults_to_none(dao):
    # When no alias is provided the column stays empty and callers fall back
    # to db_name for display.
    entity = dao.create(
        {
            "db_type": "mysql",
            "db_name": "analytics",
            "db_host": "10.0.0.2",
            "db_port": 3306,
        }
    )
    assert not entity.display_name


def test_update_alias(dao):
    dao.create(
        {
            "db_type": "mysql",
            "db_name": "warehouse",
            "display_name": "old-name",
            "db_host": "10.0.0.3",
            "db_port": 3306,
        }
    )
    created = dao.get_by_names("warehouse")

    dao.update(
        {"id": created.id},
        {"db_type": "mysql", "db_name": "warehouse", "display_name": "new-name"},
    )

    updated = dao.get_by_names("warehouse")
    assert updated.display_name == "new-name"
