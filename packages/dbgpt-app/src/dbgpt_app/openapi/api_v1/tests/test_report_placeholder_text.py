from dbgpt_app.openapi.api_v1.tools.html_interpreter import _render_placeholder_parts


def test_structured_text_and_evidence_render_as_prose():
    html = _render_placeholder_parts(
        [
            [
                {"text": "Holiday share: "},
                {"value": "7%", "artifact_id": "python-1"},
                {"text": ". <strong>Plan ahead.</strong>"},
            ]
        ]
    )
    assert "{'text':" not in html
    assert html.startswith("<p>Holiday share: ")
    assert 'data-dbgpt-artifacts="python-1"' in html
    assert "7%" in html
    assert html.endswith(". <strong>Plan ahead.</strong></p>")
