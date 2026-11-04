import pytest

from dbgpt.util.string_utils import extract_content, extract_content_open_ending


class TestExtractContent:
    """Test cases for the extract_content method."""

    def test_extract_between_markers(self):
        """Test extracting the content between two markers."""
        text = "prefix<api-call><name>t</name></api-call>suffix"
        result = extract_content(text, "<api-call>", "</api-call>")
        assert result == {6: "<name>t</name>"}

    def test_extract_between_markers_include(self):
        """Test extracting the content including both markers."""
        text = "prefix<api-call><name>t</name></api-call>suffix"
        result = extract_content(text, "<api-call>", "</api-call>", is_include=True)
        assert result == {6: "<api-call><name>t</name></api-call>"}

    def test_extract_multiple_matches(self):
        """Test extracting multiple marked elements."""
        text = "<A>1</A>mid<A>2</A>"
        assert extract_content(text, "<A>", "</A>") == {0: "1", 11: "2"}
        assert extract_content(text, "<A>", "</A>", is_include=True) == {
            0: "<A>1</A>",
            11: "<A>2</A>",
        }

    def test_missing_end_marker_returns_no_match(self):
        """Test that a missing end marker does not produce a bogus match."""
        text = "prefix<api-call>SELECT 1"
        assert extract_content(text, "<api-call>", "</api-call>") == {}
        assert extract_content(text, "<api-call>", "</api-call>", is_include=True) == {}

    def test_end_marker_directly_after_start_marker_include(self):
        """Test an empty element whose end marker directly follows the start marker.

        The search for the end marker must start at the first content character,
        otherwise the immediately adjacent end marker is never found and a bogus
        slice of the input is returned instead.
        """
        text = "x<api-call></api-call>y"
        result = extract_content(text, "<api-call>", "</api-call>", is_include=True)
        assert result == {1: "<api-call></api-call>"}

    def test_single_char_markers_include(self):
        """Test single character markers that are directly adjacent."""
        assert extract_content("ab[]cd", "[", "]", is_include=True) == {2: "[]"}


class TestExtractContentOpenEnding:
    """Test cases for the extract_content_open_ending method."""

    def test_extract_between_markers_include(self):
        """Test extracting the content including both markers."""
        text = "prefix<api-call><name>t</name></api-call>suffix"
        result = extract_content_open_ending(
            text, "<api-call>", "</api-call>", is_include=True
        )
        assert result == {6: "<api-call><name>t</name></api-call>"}

    def test_missing_end_marker_returns_rest_of_string(self):
        """Test that a missing end marker returns the rest of the string."""
        text = "prefix<api-call>SELECT 1"
        result = extract_content_open_ending(
            text, "<api-call>", "</api-call>", is_include=True
        )
        assert result == {6: "<api-call>SELECT 1"}

    def test_end_marker_directly_after_start_marker_include(self):
        """Test an empty element whose end marker directly follows the start marker."""
        text = "x<api-call></api-call>y"
        result = extract_content_open_ending(
            text, "<api-call>", "</api-call>", is_include=True
        )
        assert result == {1: "<api-call></api-call>"}

    @pytest.mark.parametrize(
        "long_string,s1,s2,is_include,expected",
        [
            ("Hello<h1>World", "<h1>", "</h1>", False, {5: "World"}),
            ("Hello<h1>World", "<h1>", "</h1>", True, {5: "<h1>World"}),
        ],
    )
    def test_open_ending_without_close(self, long_string, s1, s2, is_include, expected):
        """Test open ending extraction without the close marker."""
        assert extract_content_open_ending(long_string, s1, s2, is_include) == expected
