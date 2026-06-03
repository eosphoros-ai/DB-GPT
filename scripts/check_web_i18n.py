#!/usr/bin/env python3
"""Verify web locale key parity: en, zh, ru must expose the same i18n keys."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "locales"

PAIR = re.compile(
    r"^\s+([A-Za-z_][\w]*)\s*:\s*(?:'(?:\\'|[^'])*'|\"(?:\\.|[^\"])*\"|`(?:\\.|[^`])*`)",
    re.M,
)


def keys(path: Path) -> set[str]:
    return set(PAIR.findall(path.read_text(encoding="utf-8")))


def main() -> int:
    errors: list[str] = []
    for module in ("common", "chat", "flow"):
        en_k = keys(WEB / "en" / f"{module}.ts")
        zh_k = keys(WEB / "zh" / f"{module}.ts")
        ru_path = WEB / "ru" / f"{module}.ts"
        if not ru_path.is_file():
            errors.append(f"Missing {ru_path}")
            continue
        ru_k = keys(ru_path)
        for label, other in (("zh", zh_k), ("ru", ru_k)):
            if en_k != other:
                missing = sorted(en_k - other)
                extra = sorted(other - en_k)
                if missing:
                    errors.append(
                        f"{module}: missing in {label}: {missing[:5]}{'...' if len(missing) > 5 else ''}"
                    )
                if extra:
                    errors.append(f"{module}: extra in {label}: {extra[:5]}")

    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    print("web i18n: en/zh/ru key parity OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
