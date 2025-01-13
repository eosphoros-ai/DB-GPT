import pytest

from ..http_util import join_paths


@pytest.mark.parametrize(
    "paths, expected",
    [
        # Test basic path joining
        (["/base/path/", "sub/path"], "/base/path/sub/path"),
        # Test paths with '/' at the end and beginning
        (["/base/path/", "/sub/path/"], "/base/path/sub/path"),
        # Test empty string and normal path
        (["", "/sub/path"], "/sub/path"),
        # Test multiple slashes
        (["/base///path//", "///sub/path"], "/base/path/sub/path"),
        # Test only one non-empty path
        (["/only/path/"], "/only/path"),
        # Test all paths are empty
        (["", "", ""], "/"),
        # Test paths with spaces
        ([" /base/path/ ", " sub/path "], "/base/path/sub/path"),
        # Test paths with '.' and '..'
        (["/base/path/..", "sub/./path"], "/base/path/../sub/./path"),
        # Test numbers and special characters
        (["/123/", "/$pecial/char&/"], "/123/$pecial/char&"),
    ],
)
def test_join_paths(paths, expected):
    assert join_paths(*paths) == expected
