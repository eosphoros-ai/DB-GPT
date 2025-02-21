"""Internationalization utilities."""

import gettext
import inspect
import os
from functools import cache
from typing import Callable, Optional, Tuple

from dbgpt.configs.model_config import LOCALES_DIR, ROOT_PATH

_DOMAIN = "dbgpt"

_DEFAULT_LANGUAGE = os.getenv("LANGUAGE", "en")

_LANGUAGE_MAPPING = {
    "zh": "zh_CN",
    "zh_CN": "zh_CN",
}


def get_module_name(depth=2) -> Tuple[str, str]:
    """Get the module name of the caller."""
    frame = inspect.currentframe()
    try:
        for _ in range(depth):
            frame = frame.f_back
        module_path = inspect.getmodule(frame).__file__
        if module_path.startswith(ROOT_PATH):
            # Remove the root path
            module_path = os.path.relpath(module_path, ROOT_PATH)
        module_path = module_path.split(os.sep)[3:]
        domain = module_path[0]
        module = module_path[1]
        if module.endswith(".py"):
            module_path = module[:-3]
        return domain, module
    except Exception:
        return _DOMAIN, ""
    finally:
        del frame


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
        domain, module_name = get_module_name(depth=2)
        real_domain = (
            f"{domain}_{module_name.replace('.', '_')}" if module_name else domain
        )
        return _get_translator(real_domain, language)(message)

    return translator


def _install():
    import builtins

    builtins.__dict__["_"] = get_translator()


_ = get_translator()
