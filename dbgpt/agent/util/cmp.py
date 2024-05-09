"""Compare string utility functions."""

import string


def cmp_string_equal(
    a: str,
    b: str,
    ignore_case: bool = False,
    ignore_punctuation: bool = False,
    ignore_whitespace: bool = False,
) -> bool:
    """Compare two strings are equal or not.

    Args:
        a(str): The first string.
        b(str): The second string.
        ignore_case(bool): Ignore case or not.
        ignore_punctuation(bool): Ignore punctuation or not.
        ignore_whitespace(bool): Ignore whitespace or not.
    """
    if ignore_case:
        a = a.lower()
        b = b.lower()
    if ignore_punctuation:
        a = a.translate(str.maketrans("", "", string.punctuation))
        b = b.translate(str.maketrans("", "", string.punctuation))
    if ignore_whitespace:
        a = "".join(a.split())
        b = "".join(b.split())
    return a == b
