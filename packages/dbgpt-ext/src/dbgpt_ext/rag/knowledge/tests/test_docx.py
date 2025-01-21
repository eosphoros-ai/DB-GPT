from unittest.mock import MagicMock, patch

import pytest

from ..docx import DocxKnowledge


@pytest.fixture
def mock_docx_document():
    mock_document = MagicMock()
    mock_document.paragraphs = [
        MagicMock(text="This is the first paragraph."),
        MagicMock(text="This is the second paragraph."),
    ]
    with patch("docx.Document", return_value=mock_document):
        yield mock_document


def test_load_from_docx(mock_docx_document):
    file_path = "test_document.docx"
    knowledge = DocxKnowledge(file_path=file_path)
    documents = knowledge._load()

    assert len(documents) == 1
    assert (
        documents[0].content
        == "This is the first paragraph.\nThis is the second paragraph."
    )
    assert documents[0].metadata["source"] == file_path
