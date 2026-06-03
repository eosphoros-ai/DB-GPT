#!/usr/bin/env python3
"""Use i18n.t() for module-level t() calls; keep useTranslation t() inside components."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SKIP = {"locales", "node_modules", ".next", "app/i18n.ts"}


def fix_file(path: Path) -> bool:
    rel = path.relative_to(WEB).as_posix()
    if any(p in SKIP for p in rel.split("/")):
        return False
    text = path.read_text(encoding="utf-8")
    if "t('" not in text and 't("' not in text:
        return False
    hook_line = None
    for i, line in enumerate(text.splitlines()):
        if "useTranslation()" in line and "const" in line and "{ t }" in line:
            hook_line = i
            break
    lines = text.splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        if "i18n.t(" in line or "useTranslation" in line:
            continue
        if re.search(r"(?<![\w.])t\(\s*['\"]", line):
            module_scope = hook_line is None or i < hook_line
            top_level = line.startswith("const ") or line.startswith("  ") and ": t(" in line
            if module_scope and (top_level or hook_line is None):
                new_line = re.sub(r"(?<![\w.])t\(", "i18n.t(", line)
                if new_line != line:
                    lines[i] = new_line
                    changed = True
    if not changed:
        return False
    text = "".join(lines)
    if "import i18n from '@/app/i18n'" not in text and 'import i18n from "@/app/i18n"' not in text:
        m = re.search(r"^(import .+;\n)+", text, re.M)
        imp = "import i18n from '@/app/i18n';\n"
        text = text[: m.end()] + imp + text[m.end() :] if m else imp + text
    path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    n = 0
    for path in WEB.rglob("*"):
        if path.suffix in {".ts", ".tsx"} and fix_file(path):
            n += 1
    print(f"fix_module_t: updated {n} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
