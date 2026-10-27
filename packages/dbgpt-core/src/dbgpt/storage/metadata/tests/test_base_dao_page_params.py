"""Pagination arguments must not be used unchecked in ``BaseDao.get_list_page``.

``page`` and ``page_size`` come straight out of HTTP query parameters such as
``Query(default=1, description="current page")`` in the serve layer, and FastAPI
applies no lower bound to them. ``get_list_page`` used both without clamping, so
``page_size=0`` raised ``ZeroDivisionError`` while building ``total_pages``, and
``page=0`` (or a negative page) produced a negative SQL ``OFFSET``.
"""

from contextlib import contextmanager
from typing import Any, Iterator

import pytest

from dbgpt.storage.metadata._base_dao import BaseDao


class _RecordingQuery:
    """Minimal stand-in for a SQLAlchemy query that records the paging calls."""

    def __init__(self):
        self.offset_value = None
        self.limit_value = None

    def count(self) -> int:
        return 3

    def offset(self, value: int) -> "_RecordingQuery":
        self.offset_value = value
        return self

    def limit(self, value: int) -> "_RecordingQuery":
        self.limit_value = value
        return self

    def __iter__(self) -> Iterator[Any]:
        return iter([])


class _StubDao(BaseDao):
    """A DAO with no database behind it, only to exercise the paging math."""

    def __init__(self):
        self.query = _RecordingQuery()

    @contextmanager
    def session(self, commit: bool = True) -> Iterator[Any]:
        yield None

    def _create_query_object(self, session, query_request, desc_order_column=None):
        return self.query

    def to_response(self, entity):  # pragma: no cover - no entities are returned
        return entity


def test_page_size_zero_does_not_raise():
    dao = _StubDao()

    result = dao.get_list_page({}, page=1, page_size=0)

    assert result.page_size == 1, "a zero page size falls back to one row"
    assert result.total_count == 3
    assert result.total_pages == 3
    assert dao.query.limit_value == 1


def test_first_page_used_when_page_is_not_positive():
    dao = _StubDao()

    dao.get_list_page({}, page=0, page_size=20)
    assert dao.query.offset_value == 0

    dao2 = _StubDao()
    dao2.get_list_page({}, page=-3, page_size=20)
    assert dao2.query.offset_value >= 0, (
        "a negative OFFSET is rejected by MySQL and raises 500"
    )


def test_regular_pages_are_untouched():
    dao = _StubDao()

    result = dao.get_list_page({}, page=3, page_size=10)

    assert dao.query.offset_value == 20
    assert dao.query.limit_value == 10
    assert result.page == 3
    assert result.page_size == 10
    assert result.total_pages == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
