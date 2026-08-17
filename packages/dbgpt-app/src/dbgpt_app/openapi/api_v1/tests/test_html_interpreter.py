"""Tests for HTML template placeholder rendering."""

from dbgpt_app.openapi.api_v1.template_renderer import render_template_placeholders


def test_renders_spaced_and_lowercase_placeholders():
    template = (
        "<h1>{{ TITLE }}</h1><p>{{ lower_key }}</p><span>{{ MISSING_KEY }}</span>"
    )

    html = render_template_placeholders(
        template, {"TITLE": "Sales Report", "lower_key": "insight"}
    )

    assert html == ("<h1>Sales Report</h1><p>insight</p><span>{{ MISSING_KEY }}</span>")


def test_preserves_unknown_placeholders():
    template = "<div>{{ message }}</div><script>const t = '{{ x }}';</script>"

    html = render_template_placeholders(template, {"x": "1"})

    assert html == "<div>{{ message }}</div><script>const t = '1';</script>"


def test_does_not_evaluate_template_expressions():
    template = "<code>{{ uuid4() }}</code>"

    html = render_template_placeholders(template, {})

    assert html == template
