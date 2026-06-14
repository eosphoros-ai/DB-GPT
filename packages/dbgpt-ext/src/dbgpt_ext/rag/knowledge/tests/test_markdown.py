from unittest.mock import mock_open, patch

import pytest

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import ChunkStrategy
from dbgpt_ext.rag import ChunkParameters

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


def test_markdown_default_strategy_preserves_header_splitter():
    assert (
        MarkdownKnowledge.default_chunk_strategy()
        == ChunkStrategy.CHUNK_BY_MARKDOWN_HEADER
    )


def test_automatic_markdown_chunking_splits_oversized_header_chunks():
    chunk_size = 512
    markdown_text = "# Header 1\n```yaml\n" + "a" * 1200 + "\n" + "b" * 1200 + "\n```"
    document = Document(content=markdown_text, metadata={"source": "test.md"})

    documents = MarkdownKnowledge(file_path="test.md").extract(
        [document],
        ChunkParameters(
            chunk_strategy="Automatic",
            chunk_size=chunk_size,
            chunk_overlap=0,
        ),
    )

    chunks = documents[0].chunks
    assert len(chunks) > 1
    assert max(len(chunk.content) for chunk in chunks) <= chunk_size
    assert all(chunk.metadata["Header1"] == "Header 1" for chunk in chunks)
    assert all(chunk.metadata["source"] == "test.md" for chunk in chunks)
