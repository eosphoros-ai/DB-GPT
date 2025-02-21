from unittest.mock import MagicMock, mock_open, patch

import pytest

from ..csv import CSVKnowledge

MOCK_CSV_DATA = "id,name,age\n1,John Doe,30\n2,Jane Smith,25\n3,Bob Johnson,40"


@pytest.fixture
def mock_file_open():
    with patch("builtins.open", mock_open(read_data=MOCK_CSV_DATA)) as mock_file:
        yield mock_file


@pytest.fixture
def mock_csv_dict_reader():
    with patch("csv.DictReader", MagicMock()) as mock_csv:
        mock_csv.return_value = iter(
            [
                {"id": "1", "name": "John Doe", "age": "30"},
                {"id": "2", "name": "Jane Smith", "age": "25"},
                {"id": "3", "name": "Bob Johnson", "age": "40"},
            ]
        )
        yield mock_csv


def test_load_from_csv(mock_file_open, mock_csv_dict_reader):
    knowledge = CSVKnowledge(file_path="test_data.csv", source_column="name")
    documents = knowledge._load()
    assert len(documents) == 3
