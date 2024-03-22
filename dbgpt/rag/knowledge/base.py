"""Module for Knowledge Base."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Optional, Tuple, Type

from dbgpt.core import Document
from dbgpt.rag.text_splitter.text_splitter import (
    MarkdownHeaderTextSplitter,
    PageTextSplitter,
    ParagraphTextSplitter,
    RecursiveCharacterTextSplitter,
    SeparatorTextSplitter,
    TextSplitter,
)


class DocumentType(Enum):
    """Document Type Enum."""

    PDF = "pdf"
    CSV = "csv"
    MARKDOWN = "md"
    PPTX = "pptx"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    DATASOURCE = "datasource"


class KnowledgeType(Enum):
    """Knowledge Type Enum."""

    DOCUMENT = "DOCUMENT"
    URL = "URL"
    TEXT = "TEXT"

    @property
    def type(self):
        """Get type."""
        return DocumentType

    @classmethod
    def get_by_value(cls, value) -> "KnowledgeType":
        """Get Enum member by value.

        Args:
            value(any): value

        Returns:
            KnowledgeType: Enum member
        """
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"{value} is not a valid value for {cls.__name__}")


_STRATEGY_ENUM_TYPE = Tuple[Type[TextSplitter], List, str, str]


class ChunkStrategy(Enum):
    """Chunk Strategy Enum."""

    CHUNK_BY_SIZE: _STRATEGY_ENUM_TYPE = (
        RecursiveCharacterTextSplitter,
        [
            {
                "param_name": "chunk_size",
                "param_type": "int",
                "default_value": 512,
                "description": "The size of the data chunks used in processing.",
            },
            {
                "param_name": "chunk_overlap",
                "param_type": "int",
                "default_value": 50,
                "description": "The amount of overlap between adjacent data chunks.",
            },
        ],
        "chunk size",
        "split document by chunk size",
    )
    CHUNK_BY_PAGE: _STRATEGY_ENUM_TYPE = (
        PageTextSplitter,
        [],
        "page",
        "split document by page",
    )
    CHUNK_BY_PARAGRAPH: _STRATEGY_ENUM_TYPE = (
        ParagraphTextSplitter,
        [
            {
                "param_name": "separator",
                "param_type": "string",
                "default_value": "\\n",
                "description": "paragraph separator",
            }
        ],
        "paragraph",
        "split document by paragraph",
    )
    CHUNK_BY_SEPARATOR: _STRATEGY_ENUM_TYPE = (
        SeparatorTextSplitter,
        [
            {
                "param_name": "separator",
                "param_type": "string",
                "default_value": "\\n",
                "description": "chunk separator",
            },
            {
                "param_name": "enable_merge",
                "param_type": "boolean",
                "default_value": False,
                "description": "Whether to merge according to the chunk_size after "
                "splitting by the separator.",
            },
        ],
        "separator",
        "split document by separator",
    )
    CHUNK_BY_MARKDOWN_HEADER: _STRATEGY_ENUM_TYPE = (
        MarkdownHeaderTextSplitter,
        [],
        "markdown header",
        "split document by markdown header",
    )

    def __init__(self, splitter_class, parameters, alias, description):
        """Create a new ChunkStrategy with the given splitter_class."""
        self.splitter_class = splitter_class
        self.parameters = parameters
        self.alias = alias
        self.description = description

    def match(self, *args, **kwargs) -> TextSplitter:
        """Match and build splitter."""
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return self.value[0](*args, **kwargs)


class Knowledge(ABC):
    """Knowledge Base Class."""

    def __init__(
        self,
        path: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = None,
        data_loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Knowledge arguments."""
        self._path = path
        self._type = knowledge_type
        self._data_loader = data_loader

    def load(self) -> List[Document]:
        """Load knowledge from data_loader."""
        documents = self._load()
        return self._postprocess(documents)

    @classmethod
    @abstractmethod
    def type(cls) -> KnowledgeType:
        """Get knowledge type."""

    @classmethod
    def document_type(cls) -> Any:
        """Get document type."""
        return None

    def _postprocess(self, docs: List[Document]) -> List[Document]:
        """Post process knowledge from data_loader."""
        return docs

    @abstractmethod
    def _load(self) -> List[Document]:
        """Preprocess knowledge from data_loader."""

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return supported chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PAGE,
            ChunkStrategy.CHUNK_BY_PARAGRAPH,
            ChunkStrategy.CHUNK_BY_MARKDOWN_HEADER,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy.

        Returns:
            ChunkStrategy: default chunk strategy
        """
        return ChunkStrategy.CHUNK_BY_SIZE
