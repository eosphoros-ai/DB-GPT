"""The plugin DAOs' ``list`` must count rows *after* applying its filters.

Both ``MyPluginDao.list`` and ``PluginHubDao.list`` read ``all_count`` from the
query, then narrowed and paginated it. When the count was taken before the
filters, ``total_pages`` and the returned ``all_count`` described the whole
table instead of the filtered result, so a client that pages on ``total_pages``
walks a list of empty pages.
"""

import pytest

from dbgpt.storage.metadata import DatabaseManager
from dbgpt_serve.agent.hub.db.my_plugin_db import MyPluginDao, MyPluginEntity
from dbgpt_serve.agent.hub.db.plugin_hub_db import PluginHubDao, PluginHubEntity


def make_plugin(name: str, tenant: str) -> MyPluginEntity:
    return MyPluginEntity(
        name=name,
        file_name=f"{name}.zip",
        user_code="u",
        user_name="n",
        tenant=tenant,
        type="tool",
        version="1",
        sys_code="s",
    )


@pytest.fixture()
def plugin_db():
    # A fixture-local DatabaseManager: rebinding the shared ``db`` manager would
    # leave the process-wide engine pointing at this in-memory database for any
    # later test that expects ``db`` to be initialised elsewhere.
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:")
    MyPluginEntity.__table__.create(bind=manager.engine)
    with manager.session() as session:
        session.add_all(
            [
                make_plugin("p1", "tenant-a"),
                make_plugin("p2", "tenant-b"),
                make_plugin("p3", "tenant-b"),
                make_plugin("p4", "tenant-b"),
            ]
        )
    yield manager
    manager.engine.dispose()


@pytest.fixture()
def hub_db():
    manager = DatabaseManager()
    manager.init_db("sqlite:///:memory:")
    PluginHubEntity.__table__.create(bind=manager.engine)
    with manager.session() as session:
        session.add_all(
            [
                PluginHubEntity(name="h1", description="d", author="a"),
                PluginHubEntity(name="h2", description="d", author="b"),
            ]
        )
    yield manager
    manager.engine.dispose()


def test_list_reports_the_filtered_total(plugin_db):
    dao = MyPluginDao(db_manager=plugin_db)

    items, total_pages, all_count = dao.list(
        MyPluginEntity(tenant="tenant-a"), page=1, page_size=1
    )

    assert all_count == 1, "only tenant-a rows should be counted"
    assert total_pages == 1
    assert len(items) == 1


def test_unfiltered_list_is_unchanged(plugin_db):
    dao = MyPluginDao(db_manager=plugin_db)

    items, total_pages, all_count = dao.list(MyPluginEntity(), page=1, page_size=2)

    assert all_count == 4
    assert total_pages == 2
    assert len(items) == 2


def test_hub_list_reports_the_filtered_total(hub_db):
    dao = PluginHubDao(db_manager=hub_db)

    items, total_pages, all_count = dao.list(
        PluginHubEntity(author="a"), page=1, page_size=1
    )

    assert all_count == 1, "only author-a rows should be counted"
    assert total_pages == 1
    assert len(items) == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
