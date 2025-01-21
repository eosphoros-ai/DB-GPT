from unittest.mock import mock_open, patch

import pytest

from ..markdown import MarkdownKnowledge

MOCK_MARKDOWN_DATA = """# Header 1
This is some text under header 1.

## Header 2
This is some text under header 2.
"""


@pytest.fixture
def mock_file_open():
    with patch("builtins.open", mock_open(read_data=MOCK_MARKDOWN_DATA)) as mock_file:
        yield mock_file


# 定义测试函数
def test_load_from_markdown(mock_file_open):
    file_path = "test_document.md"
    knowledge = MarkdownKnowledge(file_path=file_path)
    documents = knowledge._load()

    assert len(documents) == 1
    assert documents[0].content == MOCK_MARKDOWN_DATA
    assert documents[0].metadata["source"] == file_path
