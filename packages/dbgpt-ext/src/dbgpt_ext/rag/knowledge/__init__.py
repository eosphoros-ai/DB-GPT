"""Module Of Knowledge."""

from typing import Any, Dict

from dbgpt_ext.rag.knowledge.factory import KnowledgeFactory

_MODULE_CACHE: Dict[str, Any] = {}


def __getattr__(name: str):
    # Lazy load
    import importlib

    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]

    _LIBS = {
        "KnowledgeFactory": "factory",
        "CSVKnowledge": "csv",
        "DatasourceKnowledge": "datasource",
        "DocxKnowledge": "docx",
        "HTMLKnowledge": "html",
        "MarkdownKnowledge": "markdown",
        "PDFKnowledge": "pdf",
        "PPTXKnowledge": "pptx",
        "StringKnowledge": "string",
        "TXTKnowledge": "txt",
        "URLKnowledge": "url",
        "ExcelKnowledge": "xlsx",
    }

    if name in _LIBS:
        module_path = "." + _LIBS[name]
        module = importlib.import_module(module_path, __name__)
        attr = getattr(module, name)
        _MODULE_CACHE[name] = attr
        return attr
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "KnowledgeFactory",
    "CSVKnowledge",
    "DatasourceKnowledge",
    "DocxKnowledge",
    "HTMLKnowledge",
    "MarkdownKnowledge",
    "PDFKnowledge",
    "PPTXKnowledge",
    "StringKnowledge",
    "TXTKnowledge",
    "URLKnowledge",
    "ExcelKnowledge",
]
