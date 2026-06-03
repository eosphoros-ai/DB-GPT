#!/usr/bin/env python3
"""Маршрутизация OpenRouter на конкретного провайдера (например Alibaba для DeepSeek)."""
from __future__ import annotations

import os
from pathlib import Path

MARKER = "# DBGPT_OPENROUTER_PROVIDER_PATCH"
TARGET = Path(
    "/app/packages/dbgpt-core/src/dbgpt/model/proxy/llms/chatgpt.py"
)

# OpenRouter принимает provider в теле JSON; OpenAI SDK — через extra_body.
PATCH_BLOCK = f"""
        {MARKER}
        _or_order = os.environ.get("OPENROUTER_PROVIDER_ORDER", "").strip()
        if _or_order:
            _providers = [p.strip() for p in _or_order.split(",") if p.strip()]
            _allow_fb = os.environ.get("OPENROUTER_ALLOW_FALLBACKS", "false").lower() in (
                "1",
                "true",
                "yes",
            )
            _eb = payload.setdefault("extra_body", {{}})
            if not isinstance(_eb, dict):
                _eb = {{}}
                payload["extra_body"] = _eb
            _eb["provider"] = {{"order": _providers, "allow_fallbacks": _allow_fb}}
"""

OLD_BROKEN_LINE = '            payload["provider"] = {"order": _providers, "allow_fallbacks": _allow_fb}'
NEW_FIXED_LINES = """            _eb = payload.setdefault("extra_body", {})
            if not isinstance(_eb, dict):
                _eb = {}
                payload["extra_body"] = _eb
            _eb["provider"] = {"order": _providers, "allow_fallbacks": _allow_fb}"""


def apply_or_fix(text: str) -> tuple[str, str]:
    if "DBGPT_OPENROUTER_NATIVE" in text:
        return text, "нативная поддержка в образе"

    if OLD_BROKEN_LINE in text:
        return text.replace(OLD_BROKEN_LINE, NEW_FIXED_LINES, 1), "исправлен extra_body"

    if MARKER in text:
        return text, "уже применён"

    needle = "        for k, v in self._openai_kwargs.items():\n            payload[k] = v"
    if needle not in text:
        return text, "якорь не найден"

    if "import os\n" not in text[:800]:
        text = text.replace("import logging\n", "import logging\nimport os\n", 1)
    text = text.replace(needle, needle + PATCH_BLOCK, 1)
    return text, "применён"


def main() -> None:
    order = os.environ.get("OPENROUTER_PROVIDER_ORDER", "").strip()
    if not order:
        print("patch_openrouter_provider: OPENROUTER_PROVIDER_ORDER не задан, пропуск")
        return
    if not TARGET.is_file():
        print(f"patch_openrouter_provider: нет файла {TARGET}")
        return

    text = TARGET.read_text(encoding="utf-8")
    new_text, status = apply_or_fix(text)
    if new_text == text and status != "уже применён":
        print(f"patch_openrouter_provider: {status}, пропуск")
        return
    if new_text != text:
        TARGET.write_text(new_text, encoding="utf-8")
    print(
        f"patch_openrouter_provider: {status}, "
        f"provider.order={order!r}, "
        f"allow_fallbacks={os.environ.get('OPENROUTER_ALLOW_FALLBACKS', 'false')}"
    )


if __name__ == "__main__":
    main()
