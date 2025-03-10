from unittest.mock import mock_open, patch

import pytest

from ..txt import TXTKnowledge

MOCK_TXT_CONTENT = b"Sample text content for testing.\nAnother line of text."

MOCK_CHARDET_RESULT = {"encoding": "utf-8", "confidence": 0.99}


@pytest.fixture
def mock_file_open():
    with patch(
        "builtins.open", mock_open(read_data=MOCK_TXT_CONTENT), create=True
    ) as mock_file:
        yield mock_file


@pytest.fixture
def mock_chardet_detect():
    with patch("chardet.detect", return_value=MOCK_CHARDET_RESULT) as mock_detect:
        yield mock_detect


# 定义测试函数
def test_load_from_txt(mock_file_open, mock_chardet_detect):
    file_path = "test_document.txt"
    knowledge = TXTKnowledge(file_path=file_path)
    documents = knowledge._load()

    assert len(documents) == 1
    assert "Sample text content for testing." in documents[0].content
    assert documents[0].metadata["source"] == file_path

    mock_file_open.assert_called_once_with(file_path, "rb")

    mock_chardet_detect.assert_called_once()
