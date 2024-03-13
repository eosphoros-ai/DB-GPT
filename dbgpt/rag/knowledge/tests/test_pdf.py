from unittest.mock import MagicMock, mock_open, patch

import pytest

from dbgpt.rag.knowledge.pdf import PDFKnowledge

MOCK_PDF_PAGES = [
    ("This is the content of the first page.", 0),
    ("This is the content of the second page.", 1),
]


@pytest.fixture
def mock_pdf_open_and_reader():
    mock_pdf_file = mock_open()
    mock_reader = MagicMock()
    mock_reader.pages = [
        MagicMock(extract_text=MagicMock(return_value=page[0]))
        for page in MOCK_PDF_PAGES
    ]
    with patch("builtins.open", mock_pdf_file):
        with patch("pypdf.PdfReader", return_value=mock_reader) as mock:
            yield mock


def test_load_from_pdf(mock_pdf_open_and_reader):
    file_path = "test_document.pdf"
    knowledge = PDFKnowledge(file_path=file_path)
    documents = knowledge._load()

    assert len(documents) == len(MOCK_PDF_PAGES)
    for i, document in enumerate(documents):
        assert MOCK_PDF_PAGES[i][0] in document.content
        assert document.metadata["source"] == file_path
        assert document.metadata["page"] == MOCK_PDF_PAGES[i][1]

    #
