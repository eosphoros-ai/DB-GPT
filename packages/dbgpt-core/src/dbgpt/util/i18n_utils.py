"""Internationalization utilities."""

import gettext
import inspect
import os
from functools import cache
from typing import Any, Callable, Optional, Tuple

try:
    from pydantic_core import SchemaSerializer, core_schema
except ImportError:
    SchemaSerializer = None
    core_schema = None

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


def is_i18n_string(value: Any) -> bool:
    if isinstance(value, LazyTranslatedString):
        return True
    return False


# Locate a .mo file using the gettext strategy
def _find(domain, localedir=None, languages=None, all=False):
    # Get some reasonable defaults for arguments that were not supplied
    if localedir is None:
        localedir = gettext._default_localedir
    if languages is None:
        languages = []
        for envar in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
            val = os.environ.get(envar)
            if val:
                languages = val.split(":")
                break
        if "C" not in languages:
            languages.append("C")
    # now normalize and expand the languages
    nelangs = []
    for lang in languages:
        for nelang in gettext._expand_lang(lang):
            if nelang not in nelangs:
                nelangs.append(nelang)
    # select a language
    if all:
        result = []
    else:
        result = None
    for lang in nelangs:
        if lang == "C":
            break
        # mofile = os.path.join(localedir, lang, 'LC_MESSAGES', '%s.mo' % domain)
        # For all mo file in localedir/lang/LC_MESSAGES
        lang_dir = os.path.join(localedir, lang, "LC_MESSAGES")
        if not os.path.exists(lang_dir):
            continue
        for file_name in os.listdir(lang_dir):
            if file_name and file_name.endswith(".mo"):
                mofile = os.path.join(lang_dir, file_name)
                if os.path.exists(mofile):
                    if all:
                        result.append(mofile)
                    else:
                        return mofile
    return result


# a mapping between absolute .mo file path and Translation object
_translations = {}
_unspecified = ["unspecified"]


def _translation(
    domain,
    localedir=None,
    languages=None,
    class_=None,
    fallback=False,
    codeset=_unspecified,
):
    if class_ is None:
        class_ = gettext.GNUTranslations
    mofiles = _find(domain, localedir, languages, all=True)
    if not mofiles:
        if fallback:
            return gettext.NullTranslations()
        from errno import ENOENT

        raise FileNotFoundError(ENOENT, "No translation file found for domain", domain)
    # Avoid opening, reading, and parsing the .mo file after it's been done
    # once.
    result = None
    for mofile in mofiles:
        key = (class_, os.path.abspath(mofile))
        t = _translations.get(key)
        if t is None:
            with open(mofile, "rb") as fp:
                t = _translations.setdefault(key, class_(fp))
        # Copy the translation object to allow setting fallbacks and
        # output charset. All other instance data is shared with the
        # cached object.
        # Delay copy import for speeding up gettext import when .mo files
        # are not used.
        import copy

        t = copy.copy(t)
        if codeset is not _unspecified:
            import warnings

            warnings.warn("parameter codeset is deprecated", DeprecationWarning, 2)
            if codeset:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", r".*\bset_output_charset\b.*", DeprecationWarning
                    )
                    t.set_output_charset(codeset)
        if result is None:
            result = t
        else:
            result.add_fallback(t)
    return result


@cache
def _get_translator(
    domain: str, language: str, read_all: bool = False
) -> Callable[[str], str]:
    try:
        if read_all:
            translation = _translation(domain, LOCALES_DIR, languages=[language])
        else:
            translation = gettext.translation(domain, LOCALES_DIR, languages=[language])

    except FileNotFoundError:
        translation = gettext.NullTranslations()

    return translation.gettext


def get_translator(language: Optional[str] = None) -> Callable[[str], str]:
    """Return a translator function."""

    def translator(message: str, domain=None, module=None) -> str:
        global _DEFAULT_LANGUAGE
        nonlocal language
        if not language:
            language = _DEFAULT_LANGUAGE
        language = _LANGUAGE_MAPPING.get(language, language)
        read_all = False
        if not domain:
            domain, module = get_module_name(depth=2)
            read_all = True
        real_domain = f"{domain}_{module.replace('.', '_')}" if module else domain
        return _get_translator(real_domain, language, read_all=read_all)(message)

    return translator


def _install():
    import builtins

    # Install the lazy translator as the global `_`
    builtins.__dict__["_"] = _


def _serialize_lazy_translated_string(value: Any, _info) -> str:
    """Custom serialization function for LazyTranslatedString."""
    if isinstance(value, LazyTranslatedString):
        # For LazyTranslatedString, return the translated string
        real_str = str(value)
        return real_str
    return value


class LazyTranslatedString(str):
    """A lazy proxy for a translated string."""

    if SchemaSerializer:
        __pydantic_serializer__ = SchemaSerializer(
            core_schema.str_schema(
                serialization=core_schema.wrap_serializer_function_ser_schema(
                    function=_serialize_lazy_translated_string
                )
            )
        )

    def __new__(cls, message: str, domain=None, module=None):
        # Create a str instance, but keep the original message
        instance = super().__new__(cls, message)
        instance._message = message
        instance._translated_message = None
        instance._last_language = None  # The last language used for translation
        instance._domain = domain
        instance._module = module
        return instance

    def _get_translated_message(self) -> str:
        """Lazily get the translated message."""
        global _DEFAULT_LANGUAGE

        # If the language has changed or the translation result has not been cached,
        # re-obtain the translation
        if self._translated_message is None or self._last_language != _DEFAULT_LANGUAGE:
            self._translated_message = get_translator()(
                str(self._message), self._domain, self._module
            )
            self._last_language = _DEFAULT_LANGUAGE  # Update the last language
        return self._translated_message

    def __str__(self) -> str:
        """Convert to string (e.g., when printing)."""
        return self._get_translated_message()

    def __repr__(self) -> str:
        """Representation for debugging."""
        return f"LazyTranslatedString({repr(self._message)})"

    def __hash__(self) -> int:
        """Ensure the hash is the same as the original message."""
        return hash(self._message)

    def __eq__(self, other) -> bool:
        """Support equality comparison."""
        if isinstance(other, LazyTranslatedString):
            return self._message == other._message
        return str(self) == str(other)

    def __bool__(self) -> bool:
        """Support truthiness testing."""
        return bool(self._message)  # for the raw string

    def __add__(self, other) -> str:
        """Support string concatenation."""
        return str(self) + str(other)

    def __radd__(self, other) -> str:
        """Support string concatenation."""
        return str(other) + str(self)

    def __len__(self) -> int:
        """Support len()."""
        return len(str(self))

    # def __getattr__(self, item):
    #     """Delegate attribute access to the translated string."""
    #     if item == "__pydantic_core_schema__" or item == "__pydantic_serializer__":
    #         return getattr(str(self), item)
    #     return getattr(str(self), item)

    def __deepcopy__(self, memo):
        """Support deepcopy.

        Dataclasses use deepcopy to clone objects, so we need to support it.
        """
        return str(self)


def _(message: str) -> str:
    """Return a lazy translated string."""
    # Record the domain and module name
    domain, module_name = get_module_name(depth=2)
    return LazyTranslatedString(message, domain=domain, module=module_name)
