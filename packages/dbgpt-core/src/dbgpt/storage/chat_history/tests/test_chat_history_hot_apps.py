"""Pagination contract of the hot-app listing behind ``/v1/app/hot/list``.

``ChatHistoryDao.list_hot_apps`` documents ``skip_page`` as a zero-based *page*
index -- its docstring says ``LIMIT (skip_page * top_k), (top_k)`` and its query
uses ``.offset(skip_page * top_k)``. ``get_hot_app_map`` takes the same
``skip_page`` argument and is called the same way by ``GptsAppDao.list_hot_apps``
(``packages/dbgpt-serve/src/dbgpt_serve/agent/db/gpts_app.py:568`` passes
``query.page - 1``), but emits ``LIMIT {skip_page}, {top_k}``, so it skips
*rows* instead of whole pages and every page after the first repeats almost all
of the previous one.
"""

import pytest
from sqlalchemy import text

from dbgpt.storage.chat_history.chat_history_db import (
    ChatHistoryDao,
    ChatHistoryEntity,
    ChatHistoryMessageEntity,
)
from dbgpt.storage.metadata import db

# app_code -> number of ranked conversations, so the ordering is fixed.
_USAGE = [("app-a", 5), ("app-b", 4), ("app-c", 3), ("app-d", 2), ("app-e", 1)]


@pytest.fixture(autouse=True)
def hot_app_db():
    """Seed an in-memory database with five published apps and their history."""
    db.init_db("sqlite:///:memory:")
    # Create only the two tables this test drives. ``db.create_all()`` walks the
    # shared metadata, so any test module that imported ``GptsAppEntity`` would
    # make the stand-in ``gpts_app`` below collide with the real table.
    ChatHistoryEntity.__table__.create(bind=db.engine)
    ChatHistoryMessageEntity.__table__.create(bind=db.engine)

    with db.session() as session:
        # Minimal stand-in for the gpts_app table the hot-app SQL joins.
        session.execute(
            text("CREATE TABLE gpts_app (app_code VARCHAR(255), published VARCHAR(64))")
        )
        for code, uses in _USAGE:
            session.execute(
                text("INSERT INTO gpts_app (app_code, published) VALUES (:c, 'true')"),
                {"c": code},
            )
            for use in range(uses):
                conv_uid = f"{code}-{use}"
                session.add(
                    ChatHistoryEntity(
                        conv_uid=conv_uid,
                        chat_mode="chat_app",
                        summary=conv_uid,
                        app_code=code,
                    )
                )
                session.add(
                    ChatHistoryMessageEntity(
                        conv_uid=conv_uid,
                        index=0,
                        round_index=0,
                        message_detail="[]",
                    )
                )
    yield


def _codes(rows):
    return [row["app_code"] for row in rows]


def test_get_hot_app_map_skips_whole_pages():
    """Page 2 starts after the first ``top_k`` ranked apps, not after 1 row."""
    dao = ChatHistoryDao()

    assert _codes(dao.get_hot_app_map(0, 2)) == ["app-a", "app-b"]
    assert _codes(dao.get_hot_app_map(1, 2)) == ["app-c", "app-d"]
    assert _codes(dao.get_hot_app_map(2, 2)) == ["app-e"]


def test_consecutive_hot_app_pages_do_not_overlap():
    """A paginated listing must not repeat rows across pages."""
    dao = ChatHistoryDao()

    first_page = _codes(dao.get_hot_app_map(0, 2))
    second_page = _codes(dao.get_hot_app_map(1, 2))

    assert set(first_page).isdisjoint(second_page)
