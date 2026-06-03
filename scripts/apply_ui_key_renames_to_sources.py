#!/usr/bin/env python3
"""Apply ui_* -> semantic renames to source files (locales already renamed)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def build_renames() -> dict[str, str]:
    diff = subprocess.check_output(
        ["git", "diff", "web/locales/en/common.ts", "web/locales/en/chat.ts", "web/locales/en/flow.ts"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    old: dict[str, str] = {}
    new: dict[str, str] = {}
    for line in diff.splitlines():
        if line.startswith("-  ui_") and ": '" in line:
            m = re.match(r"-\s+(ui_[\w]+):\s+'((?:\\'|[^'])*)'", line)
            if m:
                old[m.group(1)] = m.group(2)
        if line.startswith("+  ") and ": '" in line and not line.startswith("+++ "):
            m = re.match(r"\+\s+([A-Za-z_][\w]*):\s+'((?:\\'|[^'])*)'", line)
            if m and not m.group(1).startswith("ui_"):
                new[m.group(2)] = m.group(1)
    renames: dict[str, str] = {}
    for ok, ov in old.items():
        nk = new.get(ov)
        if nk:
            renames[ok] = nk
    return renames


def main() -> int:
    renames = build_renames()
    print(f"rename map: {len(renames)} keys")
    skip = {"node_modules", ".next", "old_web", "locales"}
    n = 0
    for path in WEB.rglob("*"):
        if path.suffix not in {".ts", ".tsx"} or skip.intersection(path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        orig = text
        for old, new in sorted(renames.items(), key=lambda x: -len(x[0])):
            text = text.replace(f"'{old}'", f"'{new}'")
            text = text.replace(f'"{old}"', f'"{new}"')
        if text != orig:
            path.write_text(text, encoding="utf-8")
            n += 1
    print(f"updated {n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
