"""Code File Knowledge - Load and split code files by AST or text."""

from typing import Any, Dict, List, Optional, Union

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import (
    ChunkStrategy,
    DocumentType,
    Knowledge,
    KnowledgeType,
)

# File extension → language mapping
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
    ".py": "python",
    ".pyw": "python",
    ".java": "java",
    ".go": "go",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hxx": "cpp",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".scala": "scala",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".swift": "swift",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".sql": "sql",
    ".proto": "protobuf",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".conf": "ini",
    ".r": "r",
    ".R": "r",
    ".lua": "lua",
    ".dart": "dart",
    ".cs": "csharp",
    ".vue": "vue",
    ".svelte": "svelte",
}

# Languages that support tree-sitter AST splitting
AST_SUPPORTED_LANGUAGES = {
    "python",
    "java",
    "javascript",
    "typescript",
    "go",
    "rust",
    "c",
    "cpp",
}


class CodeFileKnowledge(Knowledge):
    """Knowledge source for code files.

    Supports loading individual code files and selecting the appropriate
    chunk strategy based on language: AST splitting for supported languages,
    size-based splitting for others.
    """

    def __init__(
        self,
        file_path: Optional[str] = None,
        language: Optional[str] = None,
        knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT,
        loader: Optional[Any] = None,
        metadata: Optional[Dict[str, Union[str, List[str]]]] = None,
        **kwargs: Any,
    ) -> None:
        """Create CodeFileKnowledge.

        Args:
            file_path: Path to the code file.
            language: Programming language (auto-detected from extension if None).
            knowledge_type: Knowledge type.
            loader: Optional custom loader.
            metadata: Additional metadata.
        """
        super().__init__(
            path=file_path,
            knowledge_type=knowledge_type,
            data_loader=loader,
            metadata=metadata,
            **kwargs,
        )
        if language:
            self._language = language
        elif file_path:
            ext = "." + file_path.rsplit(".", 1)[-1] if "." in file_path else ""
            self._language = EXTENSION_LANGUAGE_MAP.get(ext.lower(), "text")
        else:
            self._language = "text"

    def _load(self) -> List[Document]:
        """Load code file as a Document."""
        if self._loader:
            documents = self._loader.load()
            return [Document.langchain2doc(d) for d in documents]

        if not self._path:
            raise ValueError("file_path is required")

        try:
            import chardet

            with open(self._path, "rb") as f:
                raw = f.read()
                result = chardet.detect(raw)
                encoding = result.get("encoding") or "utf-8"
                text = raw.decode(encoding, errors="ignore")
        except ImportError:
            # Fallback without chardet
            with open(self._path, encoding="utf-8", errors="ignore") as f:
                text = f.read()

        filename = self._path.rsplit("/", 1)[-1] if "/" in self._path else self._path
        doc_name = self._doc_name or filename
        metadata = {
            "source": self._path,
            "doc_name": doc_name,
            "file_type": "code",
            "language": self._language,
        }
        if self._metadata:
            metadata.update(self._metadata)

        return [Document(content=text, metadata=metadata)]

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return supported chunk strategies."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy."""
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls) -> KnowledgeType:
        """Return knowledge type."""
        return KnowledgeType.DOCUMENT

    @classmethod
    def document_type(cls) -> DocumentType:
        """Return document type."""
        return DocumentType.CODE

    @property
    def suffix(self) -> Any:
        """Get document suffix."""
        return DocumentType.CODE.value
