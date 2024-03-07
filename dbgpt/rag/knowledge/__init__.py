"""Module Of Knowledge."""

from .base import ChunkStrategy, Knowledge, KnowledgeType  # noqa: F401
from .csv import CSVKnowledge  # noqa: F401
from .docx import DocxKnowledge  # noqa: F401
from .factory import KnowledgeFactory  # noqa: F401
from .html import HTMLKnowledge  # noqa: F401
from .markdown import MarkdownKnowledge  # noqa: F401
from .pdf import PDFKnowledge  # noqa: F401
from .pptx import PPTXKnowledge  # noqa: F401
from .string import StringKnowledge  # noqa: F401
from .txt import TXTKnowledge  # noqa: F401
from .url import URLKnowledge  # noqa: F401

__ALL__ = [
    "KnowledgeFactory",
    "Knowledge",
    "KnowledgeType",
    "ChunkStrategy",
    "CSVKnowledge",
    "DocxKnowledge",
    "HTMLKnowledge",
    "MarkdownKnowledge",
    "PDFKnowledge",
    "PPTXKnowledge",
    "StringKnowledge",
    "TXTKnowledge",
    "URLKnowledge",
]
