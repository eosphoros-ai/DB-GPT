from dbgpt.util.pagination_utils import PaginationResult


def test_build_from_all_normal_case():
    items = list(range(100))
    result = PaginationResult.build_from_all(items, page=2, page_size=20)

    assert len(result.items) == 20
    assert result.items == list(range(20, 40))
    assert result.total_count == 100
    assert result.total_pages == 5
    assert result.page == 2
    assert result.page_size == 20


def test_build_from_all_empty_list():
    items = []
    result = PaginationResult.build_from_all(items, page=1, page_size=5)

    assert result.items == []
    assert result.total_count == 0
    assert result.total_pages == 0
    assert result.page == 0
    assert result.page_size == 5


def test_build_from_all_last_page():
    items = list(range(95))
    result = PaginationResult.build_from_all(items, page=5, page_size=20)

    assert len(result.items) == 15
    assert result.items == list(range(80, 95))
    assert result.total_count == 95
    assert result.total_pages == 5
    assert result.page == 5
    assert result.page_size == 20


def test_build_from_all_page_out_of_range():
    items = list(range(50))
    result = PaginationResult.build_from_all(items, page=10, page_size=10)

    assert len(result.items) == 10
    assert result.items == list(range(40, 50))
    assert result.total_count == 50
    assert result.total_pages == 5
    assert result.page == 5
    assert result.page_size == 10


def test_build_from_all_page_zero():
    items = list(range(50))
    result = PaginationResult.build_from_all(items, page=0, page_size=10)

    assert len(result.items) == 10
    assert result.items == list(range(0, 10))
    assert result.total_count == 50
    assert result.total_pages == 5
    assert result.page == 1
    assert result.page_size == 10


def test_build_from_all_negative_page():
    items = list(range(50))
    result = PaginationResult.build_from_all(items, page=-1, page_size=10)

    assert len(result.items) == 10
    assert result.items == list(range(0, 10))
    assert result.total_count == 50
    assert result.total_pages == 5
    assert result.page == 1
    assert result.page_size == 10


def test_build_from_all_page_size_larger_than_total():
    items = list(range(50))
    result = PaginationResult.build_from_all(items, page=1, page_size=100)

    assert len(result.items) == 50
    assert result.items == list(range(50))
    assert result.total_count == 50
    assert result.total_pages == 1
    assert result.page == 1
    assert result.page_size == 100
