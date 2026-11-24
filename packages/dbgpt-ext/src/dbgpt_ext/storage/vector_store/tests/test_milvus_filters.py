"""Unit tests for MilvusStore.convert_metadata_filters."""

import pytest

pytest.importorskip("pymilvus")

from dbgpt.storage.vector_store.filters import (  # noqa: E402
    FilterCondition,
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from dbgpt_ext.storage.vector_store.milvus_store import MilvusStore  # noqa: E402


def _convert(*filters: MetadataFilter, condition=FilterCondition.AND) -> str:
    # convert_metadata_filters only reads props_field, so no server is needed.
    store = MilvusStore.__new__(MilvusStore)
    store.props_field = "props_field"
    return store.convert_metadata_filters(
        MetadataFilters(condition=condition, filters=list(filters))
    )


@pytest.mark.parametrize(
    ("operator", "value", "expected"),
    [
        (FilterOperator.EQ, "a", '(props_field["k"] == "a")'),
        (FilterOperator.NE, "a", '(props_field["k"] != "a")'),
        (FilterOperator.GT, 3, '(props_field["k"] > 3)'),
        (FilterOperator.GTE, 1.5, '(props_field["k"] >= 1.5)'),
        (FilterOperator.LT, 3, '(props_field["k"] < 3)'),
        (FilterOperator.LTE, 3, '(props_field["k"] <= 3)'),
        (FilterOperator.IN, ["a", "b"], '(props_field["k"] in ["a", "b"])'),
        (FilterOperator.NIN, [1, 2], '(props_field["k"] not in [1, 2])'),
    ],
)
def test_each_operator_keeps_its_meaning(operator, value, expected):
    assert _convert(MetadataFilter(key="k", operator=operator, value=value)) == expected


def test_string_values_are_quoted():
    expr = _convert(
        MetadataFilter(key="name", value="O'Neil"),
        MetadataFilter(key="quote", value='say "hi"'),
    )
    assert expr == (
        '(props_field["name"] == "O\'Neil") and '
        '(props_field["quote"] == "say \\"hi\\"")'
    )


def test_conditions_are_joined_with_the_filter_condition():
    expr = _convert(
        MetadataFilter(key="a", operator=FilterOperator.GT, value=1),
        MetadataFilter(key="b", operator=FilterOperator.NE, value="x"),
        condition=FilterCondition.OR,
    )
    assert expr == '(props_field["a"] > 1) or (props_field["b"] != "x")'


def test_unsupported_operator_raises():
    with pytest.raises(ValueError, match="not supported"):
        _convert(MetadataFilter(key="k", operator=FilterOperator.EXISTS, value="k"))
