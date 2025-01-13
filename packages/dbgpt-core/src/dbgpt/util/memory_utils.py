from typing import Any

from pympler import asizeof


def _get_object_bytes(obj: Any) -> int:
    """Get the bytes of a object in memory

    Args:
        obj (Any): The object to return the bytes
    """
    return asizeof.asizeof(obj)
