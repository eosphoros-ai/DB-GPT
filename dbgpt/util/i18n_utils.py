"""Internationalization utilities."""

import gettext
import inspect
import os
from functools import cache
from typing import Callable, Optional

from dbgpt.configs.model_config import LOCALES_DIR, ROOT_PATH

_DOMAIN = "dbgpt"

_DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")

_LANGUAGE_MAPPING = {
    "zh": "zh_CN",
    "zh_CN": "zh_CN",
}


def get_module_name(depth=2):
    """Get the module name of the caller."""
    frame = inspect.currentframe()
    try:
        for _ in range(depth):
            frame = frame.f_back
        module_path = inspect.getmodule(frame).__file__
        if module_path.startswith(ROOT_PATH):
            module_path = module_path[len(ROOT_PATH) + 1 :]
        module_path = module_path.split("/")[1]
        if module_path.endswith(".py"):
            module_path = module_path[:-3]
    except Exception:
        module_path = ""
    finally:
        del frame
    return module_path


def set_default_language(language: str):
    global _DEFAULT_LANGUAGE
    _DEFAULT_LANGUAGE = language


@cache
def _get_translator(domain: str, language: str) -> Callable[[str], str]:
    try:
        translation = gettext.translation(domain, LOCALES_DIR, languages=[language])
    except FileNotFoundError:
        translation = gettext.NullTranslations()

    return translation.gettext


def get_translator(language: Optional[str] = None) -> Callable[[str], str]:
    """Return a translator function."""

    def translator(message: str) -> str:
        nonlocal language
        if not language:
            language = _DEFAULT_LANGUAGE
        language = _LANGUAGE_MAPPING.get(language, language)
        module_name = get_module_name(depth=2)
        domain = (
            f"{_DOMAIN}_{module_name.replace('.', '_')}" if module_name else _DOMAIN
        )
        return _get_translator(domain, language)(message)

    return translator


def _install():
    import builtins

    builtins.__dict__["_"] = get_translator()


_ = get_translator()
