from dbgpt.core import Chunk
from dbgpt.rag.text_splitter.text_splitter import (
    CharacterTextSplitter,
    MarkdownHeaderTextSplitter,
)


def test_md_header_text_splitter() -> None:
    """unit test markdown splitter by header"""

    markdown_document = (
        "# dbgpt\n\n"
        "    ## description\n\n"
        "my name is dbgpt\n\n"
        " ## content\n\n"
        "my name is aries"
    )
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on,
    )
    output = markdown_splitter.split_text(markdown_document)
    expected_output = [
        Chunk(
            content='"dbgpt-description": my name is dbgpt',
            metadata={"Header 1": "dbgpt", "Header 2": "description"},
        ),
        Chunk(
            content='"dbgpt-content": my name is aries',
            metadata={"Header 1": "dbgpt", "Header 2": "content"},
        ),
    ]
    assert [output.content for output in output] == [
        output.content for output in expected_output
    ]


def test_merge_splits() -> None:
    """Test merging splits with a given separator."""
    splitter = CharacterTextSplitter(separator=" ", chunk_size=9, chunk_overlap=2)
    splits = ["foo", "bar", "baz"]
    expected_output = ["foo bar", "baz"]
    output = splitter._merge_splits(splits, separator=" ")
    assert output == expected_output


def test_character_text_splitter() -> None:
    """Test splitting by character count."""
    text = "foo bar baz 123"
    splitter = CharacterTextSplitter(separator=" ", chunk_size=7, chunk_overlap=3)
    output = splitter.split_text(text)
    expected_output = ["foo bar", "bar baz", "baz 123"]
    assert output == expected_output


def test_character_text_splitter_empty_doc() -> None:
    """Test splitting by character count doesn't create empty documents."""
    text = "db  gpt"
    splitter = CharacterTextSplitter(separator=" ", chunk_size=2, chunk_overlap=0)
    output = splitter.split_text(text)
    expected_output = ["db", "gpt"]
    assert output == expected_output
