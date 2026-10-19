"""Selector repair changes only malformed attributes, preserving surrounding HTML."""

from html import escape

import pytest

from dbgpt.core.interface.report_html import (
    _repair_unescaped_attribute_json,
    normalize_report_html,
)

RAW = '{"artifact-A":{"field":"rows","path":[0,"value"]}}'
BAD = f'data-dbgpt-artifact-selectors="{RAW}"'
GOOD = f'data-dbgpt-artifact-selectors="{escape(RAW, quote=True)}"'


@pytest.mark.parametrize(
    "attributes",
    [(GOOD, BAD), (BAD, GOOD), (GOOD, GOOD, BAD), (GOOD, BAD, GOOD, BAD), (GOOD, GOOD)],
)
def test_mixed_attributes_preserve_entire_document(attributes):
    body = "正文之前" + "中间正文".join(
        f"<span {a}>原始结论</span>" for a in attributes
    )
    html = (
        "<!doctype html><html><head><title>完整标题</title></head><body>"
        + body
        + "</body></html>"
    )
    expected = html.replace(BAD, GOOD)
    assert _repair_unescaped_attribute_json(html) == expected
    assert normalize_report_html(html) == expected
    assert normalize_report_html(expected) == expected


def test_skipping_invalid_json_does_not_discard_prefix_before_later_repair():
    malformed = 'data-dbgpt-artifact-selectors="{not-json}"'
    html = f"<h1>保留标题</h1><span {malformed}>保留正文</span><span {BAD}>结束</span>"
    assert _repair_unescaped_attribute_json(html) == html.replace(BAD, GOOD)
