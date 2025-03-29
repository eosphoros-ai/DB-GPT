from pathlib import Path

import pytest

from ..doc import Word97DocKnowledge


@pytest.fixture
def mock_file_path():
    file_path = Path(__file__).parent / "data" / "test_mock.doc"
    return file_path.as_posix()


def test_load_from_docx(mock_file_path):
    knowledge = Word97DocKnowledge(file_path=mock_file_path)
    documents = knowledge._load()
    actual = documents[0].content.replace("\r", "\n")
    assert len(documents) == 1
    assert actual == "This is the first paragraph.\n\nThis is the second paragraph.\n"
    assert documents[0].metadata["source"] == mock_file_path
