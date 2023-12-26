from abc import abstractmethod, ABC
from enum import Enum
from typing import Optional, Any, List

from dbgpt.rag.chunk import Document
from dbgpt.rag.text_splitter.text_splitter import (
    RecursiveCharacterTextSplitter,
    MarkdownHeaderTextSplitter,
    ParagraphTextSplitter,
    CharacterTextSplitter,
    PageTextSplitter,
    SeparatorTextSplitter,
)


class DocumentType(Enum):
    PDF = "pdf"
    CSV = "csv"
    MARKDOWN = "md"
    PPTX = "pptx"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"


class KnowledgeType(Enum):
    DOCUMENT = "DOCUMENT"
    URL = "URL"
    TEXT = "TEXT"

    @property
    def type(self):
        return DocumentType

    @classmethod
    def get_by_value(cls, value):
        """Get Enum member by value"""
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"{value} is not a valid value for {cls.__name__}")


class ChunkStrategy(Enum):
    """chunk strategy"""

    CHUNK_BY_SIZE = (
        RecursiveCharacterTextSplitter,
        [
            {"param_name": "chunk_size", "param_type": "int", "default_value": 512},
            {"param_name": "chunk_overlap", "param_type": "int", "default_value": 50},
        ],
        "chunk size",
        "split document by chunk size",
    )
    CHUNK_BY_PAGE = (PageTextSplitter, [], "page", "split document by page")
    CHUNK_BY_PARAGRAPH = (
        ParagraphTextSplitter,
        [{"param_name": "separator", "param_type": "string", "default_value": "\n"}],
        "paragraph",
        "split document by paragraph",
    )
    CHUNK_BY_SEPARATOR = (
        SeparatorTextSplitter,
        [{"param_name": "separator", "param_type": "string", "default_value": "\n"}],
        "separator",
        "split document by separator",
    )
    CHUNK_BY_MARKDOWN_HEADER = (
        MarkdownHeaderTextSplitter,
        [],
        "markdown header",
        "split document by markdown header",
    )

    def __init__(self, splitter_class, parameters, alias, description):
        self.splitter_class = splitter_class
        self.parameters = parameters
        self.alias = alias
        self.description = description

    def match(self, *args, **kwargs):
        return self.value[0](*args, **kwargs)


class Knowledge(ABC):
    type: KnowledgeType = None

    def __init__(
        self,
        path: Optional[str] = None,
        knowledge_type: Optional[KnowledgeType] = None,
        data_loader: Optional = None,
        **kwargs: Any,
    ) -> None:
        """Initialize with Knowledge arguments."""
        self._path = path
        self._type = knowledge_type
        self._data_loader = data_loader

    def load(self):
        """Load knowledge from data_loader"""
        documents = self._load()
        return self._postprocess(documents)

    @classmethod
    def type(cls) -> KnowledgeType:
        """Get knowledge type"""

    @classmethod
    def document_type(cls) -> Any:
        """Get document type"""
        return None

    def _postprocess(self, docs: List[Document]) -> List[Document]:
        """Post process knowledge from data_loader"""
        return docs

    @abstractmethod
    def _load(self):
        """Preprocess knowledge from data_loader"""

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """support chunk strategy"""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_PAGE,
            ChunkStrategy.CHUNK_BY_PARAGRAPH,
            ChunkStrategy.CHUNK_BY_MARKDOWN_HEADER,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    def default_chunk_strategy(self) -> ChunkStrategy:
        return ChunkStrategy.CHUNK_BY_SIZE

    def support_chunk_strategy(self):
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]
