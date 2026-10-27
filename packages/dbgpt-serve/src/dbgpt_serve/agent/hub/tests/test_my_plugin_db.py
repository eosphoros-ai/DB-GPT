"""``MyPluginDao.list`` counts rows before applying its filters.

It reads ``all_count`` from the unfiltered query, then narrows the query and
paginates. ``total_pages`` and the returned ``all_count`` therefore describe the
whole table instead of the filtered result, so a client that pages on
``total_pages`` walks a list of empty pages.
"""

import pytest

from dbgpt.storage.metadata import db
from dbgpt_serve.agent.hub.db.my_plugin_db import MyPluginDao, MyPluginEntity


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
    db.init_db("sqlite:///:memory:")
    MyPluginEntity.__table__.create(bind=db.engine)
    with db.session() as session:
        session.add_all(
            [
                make_plugin("p1", "tenant-a"),
                make_plugin("p2", "tenant-b"),
                make_plugin("p3", "tenant-b"),
                make_plugin("p4", "tenant-b"),
            ]
        )
    yield


def test_list_reports_the_filtered_total(plugin_db):
    dao = MyPluginDao()

    items, total_pages, all_count = dao.list(
        MyPluginEntity(tenant="tenant-a"), page=1, page_size=1
    )

    assert all_count == 1, "only tenant-a rows should be counted"
    assert total_pages == 1
    assert len(items) == 1


def test_unfiltered_list_is_unchanged(plugin_db):
    dao = MyPluginDao()

    items, total_pages, all_count = dao.list(MyPluginEntity(), page=1, page_size=2)

    assert all_count == 4
    assert total_pages == 2
    assert len(items) == 2


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
