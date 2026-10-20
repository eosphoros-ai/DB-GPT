"""Line pagination must not load an entire one-line checkpoint into the LLM."""

import json

from dbgpt_app.openapi.api_v1.tools.read_file import MAX_READ_CHARS, make_read_file


def test_single_line_json_is_bounded_and_character_pages_are_lossless(tmp_path):
    directory = tmp_path / "persisted_results"
    directory.mkdir()
    path = directory / "checkpoint.json"
    source = json.dumps({"data": "中" * (MAX_READ_CHARS * 2)}, ensure_ascii=False)
    path.write_text(source, encoding="utf-8")
    read = make_read_file({"output_dir": str(tmp_path)})
    arguments = {"file_path": str(path), "limit": 100}
    parts = []
    while arguments:
        page = json.loads(read(**arguments))
        content = page["chunks"][0]["content"]
        assert len(content) < MAX_READ_CHARS + 1000
        parts.append(content.split(" | ", 1)[1].split("\n  ...", 1)[0])
        arguments = page.get("next_read")
    assert "".join(parts) == source


def test_line_offsets_still_work_and_do_not_expand_access(tmp_path):
    directory = tmp_path / "persisted_results"
    directory.mkdir()
    path = directory / "file.txt"
    path.write_text("first\nsecond\nthird\n", encoding="utf-8")
    read = make_read_file({"output_dir": str(tmp_path)})
    page = json.loads(read(str(path), offset=1, limit=1))
    content = page["chunks"][0]["content"]
    assert "2 | second" in content
    assert "1 | first" not in content
    denied = json.loads(read(str(tmp_path / "other.json")))
    assert "Access denied" in denied["chunks"][0]["content"]
