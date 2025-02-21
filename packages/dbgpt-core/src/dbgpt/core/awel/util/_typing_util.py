from typing import Any


def _parse_bool(v: Any) -> bool:
    """Parse a value to bool."""
    if v is None:
        return False
    if str(v).lower() in ["false", "0", "", "no", "off"]:
        return False
    return bool(v)
