from dbgpt.agent.resource.tool.base import tool
from dbgpt.agent.resource.tool.pack import ToolPack

from ..react_action import ReActAction


def _make_resource(*tool_funcs):
    tools = [fn._tool for fn in tool_funcs]
    return ToolPack(tools)


@tool(description="Execute Python code")
def code_interpreter(code: str) -> str:
    """Execute Python code."""
    return code


@tool(description="Render HTML content as a web report")
def html_interpreter(html: str, title: str = "Report") -> str:
    """Render HTML content as a web report."""
    return html


class TestSingleParam:
    def test_simple_json_like(self):
        resource = _make_resource(code_interpreter)
        raw = '{"code": "print(1)"}'
        result = ReActAction._fallback_parse_args("code_interpreter", raw, resource)
        assert result == {"code": "print(1)"}

    def test_code_with_newlines_and_quotes(self):
        resource = _make_resource(code_interpreter)
        raw = (
            '{"code": "import pandas as pd\\n'
            'df = pd.read_csv(\\"data.csv\\")\\nprint(df.head())"}'
        )
        result = ReActAction._fallback_parse_args("code_interpreter", raw, resource)
        assert "import pandas as pd" in result["code"]
        assert 'pd.read_csv("data.csv")' in result["code"]

    def test_raw_string_fallback(self):
        resource = _make_resource(code_interpreter)
        raw = "print('hello world')"
        result = ReActAction._fallback_parse_args("code_interpreter", raw, resource)
        assert result == {"code": "print('hello world')"}


class TestMultiParam:
    def test_title_first_html_second(self):
        resource = _make_resource(html_interpreter)
        raw = (
            '{"title": "Walmart销售数据分析报告", '
            '"html": "<!DOCTYPE html>\\n<html lang=\\"zh-CN\\">\\n'
            "<head><title>Report</title></head>\\n"
            '<body><h1>Hello</h1></body>\\n</html>"}'
        )
        result = ReActAction._fallback_parse_args("html_interpreter", raw, resource)
        assert result.get("title") == "Walmart销售数据分析报告"
        assert "<!DOCTYPE html>" in result.get("html", "")
        assert "<h1>Hello</h1>" in result.get("html", "")

    def test_html_first_title_second(self):
        resource = _make_resource(html_interpreter)
        raw = '{"html": "<h1>Report</h1>", "title": "My Report"}'
        result = ReActAction._fallback_parse_args("html_interpreter", raw, resource)
        assert result.get("html") == "<h1>Report</h1>"
        assert result.get("title") == "My Report"

    def test_html_with_embedded_quotes_and_css(self):
        resource = _make_resource(html_interpreter)
        html_content = (
            "<div style=\\\"color: red; font-family: \\'Arial\\'\\\">Hello</div>"
        )
        raw = '{"title": "Styled Report", "html": "' + html_content + '"}'
        result = ReActAction._fallback_parse_args("html_interpreter", raw, resource)
        assert result.get("title") == "Styled Report"
        assert "Hello" in result.get("html", "")

    def test_long_html_with_many_quotes(self):
        resource = _make_resource(html_interpreter)
        html_body = (
            "<!DOCTYPE html>\\n"
            '<html lang=\\"zh-CN\\">\\n'
            "<head>\\n"
            '  <meta charset=\\"UTF-8\\">\\n'
            "  <style>\\n"
            "    body { font-family: Arial; }\\n"
            '    .card { border: 1px solid \\"#ccc\\"; }\\n'
            "  </style>\\n"
            "</head>\\n"
            "<body>\\n"
            '  <div class=\\"card\\">\\n'
            "    <h1>Sales Report</h1>\\n"
            "    <p>Total: $1,234,567</p>\\n"
            "  </div>\\n"
            "</body>\\n"
            "</html>"
        )
        raw = '{"title": "Sales Analysis", "html": "' + html_body + '"}'
        result = ReActAction._fallback_parse_args("html_interpreter", raw, resource)
        assert result.get("title") == "Sales Analysis"
        html_val = result.get("html", "")
        assert "<!DOCTYPE html>" in html_val
        assert "Sales Report" in html_val
        assert "</html>" in html_val

    def test_title_omitted_only_html(self):
        resource = _make_resource(html_interpreter)
        raw = '{"html": "<p>Simple report</p>"}'
        result = ReActAction._fallback_parse_args("html_interpreter", raw, resource)
        assert "<p>Simple report</p>" in result.get("html", "")

    def test_html_fallback_extraction_repairs_truncated_html(self):
        raw = (
            '{"html": "<!DOCTYPE html><html><body><div class="card">Hello</div>", '
            '"title": "Broken Report"}'
        )

        result = ReActAction._extract_html_interpreter_args(raw)

        assert result["title"] == "Broken Report"
        assert '<div class="card">Hello</div>' in result["html"]
        assert result["html"].endswith("</body></html>")


class TestEdgeCases:
    def test_unknown_tool_returns_empty(self):
        resource = _make_resource(code_interpreter)
        result = ReActAction._fallback_parse_args(
            "nonexistent_tool", '{"code": "x"}', resource
        )
        assert result == {}

    def test_none_resource_returns_empty(self):
        result = ReActAction._fallback_parse_args(
            "code_interpreter", '{"code": "x"}', None
        )
        assert result == {}

    def test_empty_input_returns_empty(self):
        resource = _make_resource(code_interpreter)
        result = ReActAction._fallback_parse_args("code_interpreter", "", resource)
        assert result == {}
