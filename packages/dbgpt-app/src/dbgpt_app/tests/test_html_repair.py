import asyncio

from dbgpt_app.openapi.api_v1.html_repair import (
    prepare_renderable_html,
    repair_html_if_needed,
    validate_html_integrity,
)


def test_prepare_renderable_html_wraps_fragment_and_closes_tags():
    html = '<div class="card"><h1>运营报告</h1><section><p>总数 5 < 10'

    repaired = prepare_renderable_html(html, title="运营报告")
    validation = validate_html_integrity(repaired)

    assert validation.is_valid
    assert repaired.startswith("<!DOCTYPE html>")
    assert "<title>运营报告</title>" in repaired
    assert "<body>" in repaired
    assert '<div class="card">' in repaired
    assert repaired.endswith("</body></html>")


def test_prepare_renderable_html_unwraps_markdown_and_normalizes_escaped_tags():
    html = """```html
<!DOCTYPE html>
<html><head><style>body { color: #111; }<\\/style></head>
<body><script>window.reportReady = true;<\\/script><main>OK</main>
</body></html>
```"""

    repaired = prepare_renderable_html(html, title="Report")
    validation = validate_html_integrity(repaired)

    assert validation.is_valid
    assert "```" not in repaired
    assert "</style>" in repaired
    assert "</script>" in repaired


def test_prepare_renderable_html_keeps_valid_document_content():
    html = (
        "<!DOCTYPE html><html><head><title>Existing</title></head>"
        "<body><main><h1>Ready</h1></main></body></html>"
    )

    repaired = prepare_renderable_html(html, title="Ignored")

    assert repaired == html


def test_validate_html_integrity_detects_fragment_before_repair():
    html = "<section><h1>运营报告</h1><p>缺少文档外壳"

    validation = validate_html_integrity(html)

    assert not validation.is_valid
    assert {"doctype", "html", "head", "body"}.issubset(
        set(validation.missing_required_tags)
    )


def test_repair_html_if_needed_uses_ai_repair_before_local_fallback():
    html = "<html><body><main><h1>运营报告</h1>"
    calls = []

    async def ai_repair(raw_html, validation):
        calls.append((raw_html, validation.issues))
        return (
            "<!DOCTYPE html><html><head><title>AI Fixed</title></head>"
            "<body><main><h1>运营报告</h1></main></body></html>"
        )

    repaired = asyncio.run(
        repair_html_if_needed(html, title="运营报告", ai_repair=ai_repair)
    )

    assert calls
    assert validate_html_integrity(repaired).is_valid
    assert "<title>AI Fixed</title>" in repaired
