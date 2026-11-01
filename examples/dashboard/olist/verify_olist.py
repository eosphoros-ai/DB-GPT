"""Verify Olist business answers on SQLite or MySQL."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

try:
    from .gold_queries import execute_gold_queries
except ImportError:  # Support ``python examples/dashboard/olist/verify_olist.py``.
    from gold_queries import execute_gold_queries

ROOT = Path(__file__).resolve().parent
GOLD_PATH = ROOT / "gold_answers.json"


def _compare(actual: Any, expected: Any, path: str = "answers") -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            raise AssertionError(f"{path}: object keys differ")
        for key, value in expected.items():
            _compare(actual[key], value, f"{path}.{key}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise AssertionError(
                f"{path}: expected {len(expected)} rows, got {len(actual)}"
            )
        for index, value in enumerate(expected):
            _compare(actual[index], value, f"{path}[{index}]")
        return
    if isinstance(expected, float):
        if not isinstance(actual, (float, int)) or not math.isclose(
            float(actual), expected, rel_tol=1e-9, abs_tol=1e-4
        ):
            raise AssertionError(f"{path}: expected {expected}, got {actual}")
        return
    if actual != expected:
        raise AssertionError(f"{path}: expected {expected!r}, got {actual!r}")


def verify(url: str) -> dict[str, list[dict[str, Any]]]:
    expected = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    engine = create_engine(url, future=True, pool_pre_ping=True)
    try:
        actual = execute_gold_queries(engine)
    finally:
        engine.dispose()
    _compare(actual, expected)
    for name, rows in actual.items():
        print(f"PASS {name:<22} {len(rows):>3} row(s)")
    print(f"Verified {len(actual)} Olist business questions on {url.split(':', 1)[0]}")
    return actual


def main() -> None:
    parser = argparse.ArgumentParser()
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--sqlite", type=Path)
    destination.add_argument("--mysql-url")
    args = parser.parse_args()
    if args.sqlite:
        url = f"sqlite:///{args.sqlite.resolve().as_posix()}"
    else:
        url = args.mysql_url
    verify(url)


if __name__ == "__main__":
    main()
