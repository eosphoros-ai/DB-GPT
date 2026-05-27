#!/usr/bin/env python3
"""Phase 2: replace hardcoded Chinese UI strings with t('key') and extend en/zh/ru locales."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOCALES = WEB / "locales"
DEPLOY = ROOT.parent.parent / "DBTGPT" / "deploy" / "locales"

PAIR = re.compile(
    r"^\s+([A-Za-z_][\w]*)\s*:\s*(?:'((?:\\'|[^'])*)'|\"((?:\\.|[^\"])*)\"|`((?:\\.|[^`])*)`)",
    re.M,
)
CJK = re.compile(r"[\u4e00-\u9fff]")
STRING_LIT = re.compile(r"(?P<q>['\"])(?P<body>(?:\\.|(?!\1).)*?)\1")
TEMPLATE_LIT = re.compile(r"`([^`]*[\u4e00-\u9fff][^`]*)`")
JSX_TEXT = re.compile(r">([^<>{}]*[\u4e00-\u9fff][^<>{}]*)<")
JSX_MIXED = re.compile(r"(\{[^}]+\})\s*([\u4e00-\u9fff][^<{}]*)<")
JSX_LINE_TEXT = re.compile(r"^(\s+)([\u4e00-\u9fff][^\n<{]+)\s*$", re.M)

INVALID_SNIPPET = re.compile(
    r"className|useState|useEffect|function\s|=>|import\s|/\*\*|;\s*\n|Form\.|router\.|set[A-Z]"
)

SKIP_DIRS = {"locales", "node_modules", ".next", "old_web"}
SKIP_FILES = {"next.config.js"}

MODULE_BY_PATH = [
    (re.compile(r"web/(pages|new-components|components)/chat"), "chat"),
    (re.compile(r"web/(pages|components)/construct/flow"), "flow"),
    (re.compile(r"web/components/flow"), "flow"),
]


def parse_locale_module(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return {m.group(1): (m.group(2) or m.group(3) or m.group(4) or "") for m in PAIR.finditer(path.read_text(encoding="utf-8"))}


def load_merged_locales() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    en: dict[str, str] = {}
    zh: dict[str, str] = {}
    ru: dict[str, str] = {}
    mod_of: dict[str, str] = {}
    for mod in ("common", "chat", "flow"):
        for lang, bucket in (("en", en), ("zh", zh), ("ru", ru)):
            data = parse_locale_module(LOCALES / lang / f"{mod}.ts")
            for k, v in data.items():
                bucket[k] = v
                mod_of[k] = mod
    return en, zh, ru, mod_of


def load_zh_ru() -> dict[str, str]:
    p = DEPLOY / "replacements" / "all_zh_ru.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def load_en_to_ru() -> dict[str, str]:
    p = DEPLOY / "translations" / "en_to_ru.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def pick_module(rel: str) -> str:
    for pat, mod in MODULE_BY_PATH:
        if pat.search(rel.replace("\\", "/")):
            return mod
    return "common"


def zh_to_en(zh: str, zh_val_to_key: dict[str, str], en: dict[str, str], zh_ru: dict[str, str], ru_to_en: dict[str, str]) -> str:
    if zh in zh_val_to_key:
        k = zh_val_to_key[zh]
        if k in en and en[k]:
            return en[k]
    ru = zh_ru.get(zh)
    if ru and ru in ru_to_en:
        return ru_to_en[ru]
    return zh


def make_key(text: str, en_label: str, existing: set[str]) -> str:
    if en_label and en_label != text and not CJK.search(en_label):
        base = re.sub(r"[^a-zA-Z0-9]+", "_", en_label).strip("_")
        if len(base) > 48:
            base = base[:48].rstrip("_")
        if base and re.match(r"^[A-Za-z]", base):
            cand = base if base[0].isupper() else base[0].upper() + base[1:]
            if cand not in existing:
                return cand
    h = hashlib.md5(text.encode()).hexdigest()[:8]
    cand = f"ui_{h}"
    n = 2
    while cand in existing:
        cand = f"ui_{h}_{n}"
        n += 1
    return cand


def escape_ts(s: str, quote: str = "'") -> str:
    s = s.replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r")
    if quote == "'":
        return s.replace("'", "\\'")
    return s.replace('"', '\\"')


def is_comment_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("//") or s.startswith("*") or s.startswith("/*")


def in_block_comment(text: str, pos: int) -> bool:
    before = text[:pos]
    opens = before.count("/*") - before.count("*/")
    return opens > 0 and before.rfind("*/") < before.rfind("/*")


def collect_files() -> list[Path]:
    out: list[Path] = []
    for p in WEB.rglob("*"):
        if not p.is_file() or p.suffix not in {".ts", ".tsx"}:
            continue
        rel = p.relative_to(WEB)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if p.name in SKIP_FILES:
            continue
        out.append(p)
    return sorted(out)


def ensure_use_translation(content: str) -> str:
    if "useTranslation" in content or "from '@/app/i18n'" in content or 'from "@/app/i18n"' in content:
        return content
    if not re.search(r"\bt\s*\(", content):
        return content
    if "react-i18next" not in content:
        imp = "import { useTranslation } from 'react-i18next';\n"
        m = re.search(r"^(import .+;\n)+", content, re.M)
        if m:
            content = content[: m.end()] + imp + content[m.end() :]
        else:
            content = imp + content
    if not re.search(r"const\s*\{\s*t\s*\}\s*=\s*useTranslation", content):
        # insert after first function component opening
        patterns = [
            r"(export\s+(?:default\s+)?function\s+\w+[^{]*\{)",
            r"(const\s+\w+\s*[:=]\s*(?:React\.)?(?:memo\()?function[^{]*\{)",
            r"(const\s+\w+\s*[:=]\s*\([^)]*\)\s*=>\s*\{)",
        ]
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                insert_at = m.end()
                content = content[:insert_at] + "\n  const { t } = useTranslation();" + content[insert_at:]
                break
        else:
            # top-level util: use i18n singleton
            if "import i18n from '@/app/i18n'" not in content:
                content = "import i18n from '@/app/i18n';\n" + content
            content = re.sub(r"\bt\s*\(", "i18n.t(", content)
    return content


def append_keys(mod: str, new_entries: dict[str, tuple[str, str, str]]) -> None:
    if not new_entries:
        return
    for lang, idx in (("en", 0), ("zh", 1), ("ru", 2)):
        path = LOCALES / lang / f"{mod}.ts"
        text = path.read_text(encoding="utf-8")
        block = "\n  // phase2 i18n\n"
        for key in sorted(new_entries):
            val = escape_ts(new_entries[key][idx])
            block += f"  {key}: '{val}',\n"
        stripped = text.rstrip()
        if stripped.endswith("} as const;"):
            text = stripped[: -len("} as const;")] + block + "\n} as const;\n"
        elif stripped.endswith("};"):
            text = stripped[: -2] + block + "\n};\n"
        else:
            raise SystemExit(f"Unexpected locale footer: {path}")
        path.write_text(text, encoding="utf-8")


def process_file(
    path: Path,
    en: dict[str, str],
    zh: dict[str, str],
    ru: dict[str, str],
    mod_of: dict[str, str],
    zh_val_to_key: dict[str, str],
    zh_ru: dict[str, str],
    ru_to_en: dict[str, str],
    new_by_mod: dict[str, dict[str, tuple[str, str, str]]],
    existing_keys: set[str],
) -> int:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    text = path.read_text(encoding="utf-8")
    if not CJK.search(text):
        return 0
    mod = pick_module(rel)
    replacements: list[tuple[int, int, str]] = []

    def valid_ui_string(zh_text: str) -> bool:
        if not CJK.search(zh_text) or "{{" in zh_text:
            return False
        if len(zh_text) > 200 or "\n" in zh_text:
            return False
        if INVALID_SNIPPET.search(zh_text):
            return False
        if zh_text.count("'") > 2 or zh_text.count('"') > 2:
            return False
        return True

    def resolve_key(zh_text: str) -> str | None:
        if not valid_ui_string(zh_text):
            return None
        key = zh_val_to_key.get(zh_text)
        if not key:
            key = make_key(zh_text, zh_to_en(zh_text, zh_val_to_key, en, zh_ru, ru_to_en), existing_keys)
            en_t = zh_to_en(zh_text, zh_val_to_key, en, zh_ru, ru_to_en)
            if en_t == zh_text and zh_text in zh_ru:
                for e, r in ru_to_en.items():
                    if r == zh_ru[zh_text]:
                        en_t = e
                        break
            ru_t = zh_ru.get(zh_text, en_t if en_t != zh_text else zh_text)
            if key not in en:
                new_by_mod.setdefault(mod, {})[key] = (en_t, zh_text, ru_t)
                en[key] = en_t
                zh[key] = zh_text
                ru[key] = ru_t
                mod_of[key] = mod
                existing_keys.add(key)
                zh_val_to_key[zh_text] = key
        return key

    # string literals
    for m in STRING_LIT.finditer(text):
        if in_block_comment(text, m.start()):
            continue
        line_start = text.rfind("\n", 0, m.start()) + 1
        line = text[line_start : text.find("\n", m.start())]
        if is_comment_line(line):
            continue
        body = m.group("body")
        body_unesc = body.replace("\\'", "'").replace('\\"', '"').replace("\\n", "\n")
        if CJK.search(body_unesc):
            key = resolve_key(body_unesc)
            if key:
                before = text[max(0, m.start() - 3) : m.start()]
                kind = "attr" if before.rstrip().endswith("=") else "str"
                replacements.append((m.start(), m.end(), key, kind))

    # jsx text nodes
    for m in JSX_TEXT.finditer(text):
        inner = m.group(1).strip()
        if inner and CJK.search(inner) and not inner.startswith("{"):
            key = resolve_key(inner)
            if key:
                replacements.append((m.start(1), m.end(1), key, "jsx"))

    # template literals (single-line only)
    for m in TEMPLATE_LIT.finditer(text):
        raw = m.group(1)
        if "\n" in raw or "${" in raw:
            continue
        key = resolve_key(raw)
        if key:
            replacements.append((m.start(), m.end(), key, "str"))

    # jsx: indented Chinese-only lines (e.g. button labels)
    for m in JSX_LINE_TEXT.finditer(text):
        line_start = text.rfind("\n", 0, m.start()) + 1
        if is_comment_line(text[line_start : m.start()] + m.group(2)):
            continue
        inner = m.group(2).strip()
        key = resolve_key(inner)
        if key:
            replacements.append((m.start(2), m.end(2), key, "jsx"))

    # jsx: {expr} 中文
    for m in JSX_MIXED.finditer(text):
        expr, tail = m.group(1), m.group(2).strip()
        key = resolve_key(tail)
        if key:
            replacements.append(
                (m.start(2), m.end(2), key, "jsx_expr", expr)
            )

    if not replacements:
        return 0
    replacements.sort(key=lambda x: x[0], reverse=True)
    for item in replacements:
        if len(item) == 5:
            start, end, key, kind, expr = item
        else:
            start, end, key, kind = item
            expr = None
        if kind == "jsx":
            repl = f"{{t('{key}')}}"
        elif kind == "jsx_expr":
            repl = f"{{{expr}}}{{t('{key}')}}"
        elif kind == "attr":
            repl = f"{{t('{key}')}}"
        else:
            repl = f"t('{key}')"
        text = text[:start] + repl + text[end:]
    text = ensure_use_translation(text)
    path.write_text(text, encoding="utf-8")
    return len(replacements)


def main() -> int:
    en, zh, ru, mod_of = load_merged_locales()
    zh_val_to_key = {v: k for k, v in zh.items() if v}
    zh_ru = load_zh_ru()
    en_to_ru = load_en_to_ru()
    ru_to_en = {v: k for k, v in en_to_ru.items() if v}
    existing_keys = set(en)
    new_by_mod: dict[str, dict[str, tuple[str, str, str]]] = {}
    total = 0
    for path in collect_files():
        total += process_file(
            path, en, zh, ru, mod_of, zh_val_to_key, zh_ru, ru_to_en, new_by_mod, existing_keys
        )
    for mod, entries in new_by_mod.items():
        append_keys(mod, entries)
    print(f"phase2: {total} replacements, {sum(len(v) for v in new_by_mod.values())} new keys")
    for mod, entries in sorted(new_by_mod.items()):
        print(f"  {mod}: +{len(entries)} keys")
    return 0


if __name__ == "__main__":
    sys.exit(main())
