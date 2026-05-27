#!/usr/bin/env python3
"""Refresh ru locale values from en using deploy dictionaries; fix CJK/garbled ru strings."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / "web" / "locales"
# Prefer sibling DBTGPT deploy repo; fallback to OriginalDBTGPT/DBTGPT layout.
_deploy_candidates = [
    ROOT.parent.parent / "DBTGPT" / "deploy" / "locales",
    Path(r"z:\Projects\DBTGPT\deploy\locales"),
]
DEPLOY = next((p for p in _deploy_candidates if p.is_dir()), _deploy_candidates[0])
CJK = re.compile(r"[\u4e00-\u9fff]")
PAIR = re.compile(r"^\s+([A-Za-z_][\w]*)\s*:\s*'((?:\\'|[^'])*)'", re.M)

# Overrides for upstream-neutral copy (no deploy-specific DB names)
RU_OVERRIDES: dict[str, str] = {
    "example_db_profile_report_desc": "Подключитесь к БД, постройте профиль и интерактивный HTML-отчёт",
    "example_db_profile_report_query": (
        "Проанализируйте подключённую базу данных: профиль (таблицы, поля, объёмы) "
        "и подготовьте интерактивный HTML-отчёт."
    ),
    "example_fin_report_desc": "Анализ годового отчёта компании с визуализацией данных",
    "example_fin_report_query": (
        "Проведите углублённый анализ приложенного годового отчёта: выручка, прибыль, "
        "структура активов и обязательств, денежные потоки и ключевые показатели. "
        "Сформируйте профессиональный интерактивный HTML-отчёт."
    ),
    "ui_8adc0e10": "sample_annual_report_2019.pdf",
}


def load_json(path: Path) -> dict[str, str]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def parse_ts(path: Path) -> dict[str, str]:
    return dict(PAIR.findall(path.read_text(encoding="utf-8")))


def write_ts_values(path: Path, updates: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for key, val in updates.items():
        esc = val.replace("\\", "\\\\").replace("'", "\\'")
        text, n = re.subn(
            rf"^(\s+{re.escape(key)}\s*:\s*)'(?:\\'|[^'])*'",
            rf"\1'{esc}'",
            text,
            count=1,
            flags=re.M,
        )
        if not n:
            print(f"warn: key not patched in {path.name}: {key}")
    path.write_text(text, encoding="utf-8")


def en_to_ru_value(en_val: str, zh_val: str, en_to_ru: dict[str, str], zh_ru: dict[str, str]) -> str | None:
    if en_val in RU_OVERRIDES:
        return RU_OVERRIDES[en_val]
    if en_val in en_to_ru:
        return en_to_ru[en_val]
    if zh_val in zh_ru:
        cand = zh_ru[zh_val]
        if not CJK.search(cand):
            return cand
    # partial: en phrase contained in dict keys
    for en_phrase, ru_phrase in sorted(en_to_ru.items(), key=lambda x: -len(x[0])):
        if len(en_phrase) > 3 and en_phrase in en_val and not CJK.search(ru_phrase):
            return en_val.replace(en_phrase, ru_phrase)
    return None


def main() -> int:
    en_to_ru = load_json(DEPLOY / "translations" / "en_to_ru.json")
    zh_ru = load_json(DEPLOY / "replacements" / "all_zh_ru.json")
    total = 0
    for mod in ("common", "chat", "flow"):
        en = parse_ts(LOCALES / "en" / f"{mod}.ts")
        zh = parse_ts(LOCALES / "zh" / f"{mod}.ts")
        ru = parse_ts(LOCALES / "ru" / f"{mod}.ts")
        updates: dict[str, str] = {}
        for key in ru:
            if key not in en:
                continue
            en_v, zh_v, ru_v = en[key], zh.get(key, ""), ru[key]
            if key in RU_OVERRIDES:
                updates[key] = RU_OVERRIDES[key]
                continue
            needs = (
                CJK.search(ru_v)
                or ("успешно" in ru_v and " " not in ru_v.strip())
                or ru_v == en_v
            )
            if not needs and not key.startswith("ui_"):
                continue
            new_ru = en_to_ru_value(en_v, zh_v, en_to_ru, zh_ru)
            if new_ru and new_ru != ru_v:
                updates[key] = new_ru
            elif needs and not CJK.search(en_v) and ru_v != en_v:
                updates[key] = en_v
        if updates:
            write_ts_values(LOCALES / "ru" / f"{mod}.ts", updates)
            total += len(updates)
            print(f"{mod}: updated {len(updates)} ru strings")
    print(f"total ru updates: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
