#!/usr/bin/env python3
"""Подготовка web перед yarn compile: ru по умолчанию, zh/en без изменений."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def patch_i18n_ts(web_dir: Path) -> None:
    i18n = web_dir / "app" / "i18n.ts"
    if not i18n.is_file():
        return
    text = i18n.read_text(encoding="utf-8")
    # Убедиться, что zh подключён (оригинальный китайский из репозитория)
    if "import zh from '@/locales/zh'" not in text:
        print("prepare_web: WARN — нет import zh в i18n.ts")
    if "supportedLngs" in text and "'zh'" not in text:
        text = text.replace(
            "supportedLngs: ['en', 'ru']",
            "supportedLngs: ['en', 'zh', 'ru']",
        )
    if "lng: 'ru'" not in text:
        text = text.replace("lng: 'en',", "lng: 'ru',")
        text = text.replace('lng: "en",', "lng: 'ru',")
    if "fallbackLng: 'ru'" not in text:
        text = text.replace("lng: 'ru',", "lng: 'ru',\n  fallbackLng: 'ru',")
    i18n.write_text(text, encoding="utf-8")
    print("prepare_web: i18n.ts — ru default, en/zh/ru в supportedLngs")


def patch_app_default_lang(web_dir: Path) -> None:
    app = web_dir / "pages" / "_app.tsx"
    if not app.is_file():
        return
    text = app.read_text(encoding="utf-8")
    if "stored ?? '') ? stored : 'ru'" in text:
        return
    text = text.replace(
        "isAppLanguage(stored ?? '') ? stored : 'zh'",
        "isAppLanguage(stored ?? '') ? stored : 'ru'",
    )
    text = text.replace(
        "isAppLanguage(stored ?? '') ? stored : 'en'",
        "isAppLanguage(stored ?? '') ? stored : 'ru'",
    )
    app.write_text(text, encoding="utf-8")
    print("prepare_web: _app.tsx — default ru")


def patch_next_config(web_dir: Path) -> None:
    cfg = web_dir / "next.config.js"
    if not cfg.is_file():
        return
    text = cfg.read_text(encoding="utf-8")
    if "ignoreDuringBuilds" in text:
        return
    needle = "typescript: {\n    ignoreBuildErrors: true,\n  },"
    if needle in text:
        text = text.replace(
            needle,
            needle + "\n  eslint: {\n    ignoreDuringBuilds: true,\n  },",
        )
        cfg.write_text(text, encoding="utf-8")
        print("prepare_web: next.config.js — eslint.ignoreDuringBuilds")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: prepare_web_deploy.py <web_dir>")
        sys.exit(1)
    web_dir = Path(sys.argv[1]).resolve()
    if not (web_dir / "locales" / "ru").is_dir():
        print(f"prepare_web: нет {web_dir}/locales/ru")
        sys.exit(1)
    if not (web_dir / "locales" / "zh").is_dir():
        print(f"prepare_web: нет {web_dir}/locales/zh — китайский UI будет недоступен")
        sys.exit(1)
    # Опционально: zh=ru только если явно задано (для старых lng=zh в localStorage)
    print("prepare_web: locales/zh — оригинальный китайский (без замены на ru)")
    patch_i18n_ts(web_dir)
    patch_app_default_lang(web_dir)
    patch_next_config(web_dir)
    print("prepare_web: готово")


if __name__ == "__main__":
    main()
