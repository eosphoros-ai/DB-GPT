"""URL Knowledge."""

from typing import Any, List, Optional

from dbgpt.core import Document
from dbgpt.rag.knowledge.base import ChunkStrategy, Knowledge, KnowledgeType


class URLKnowledge(Knowledge):
    """URL Knowledge."""

    def __init__(
        self,
        url: str = "",
        knowledge_type: KnowledgeType = KnowledgeType.URL,
        source_column: Optional[str] = None,
        encoding: Optional[str] = "utf-8",
        loader: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """Create URL Knowledge with Knowledge arguments.

        Args:
            url(str,  optional): url
            knowledge_type(KnowledgeType, optional): knowledge type
            source_column(str, optional): source column
            encoding(str, optional): csv encoding
            loader(Any, optional): loader
        """
        super().__init__(
            path=url, knowledge_type=knowledge_type, loader=loader, **kwargs
        )
        self._encoding = encoding
        self._source_column = source_column

    def _load(self) -> List[Document]:
        """Fetch URL document from loader."""
        if self._loader:
            documents = self._loader.load()
            return [Document.langchain2doc(lc_document) for lc_document in documents]
        else:
            if self._path is None:
                raise ValueError("web_path cannot be None")

            return self._load_document_default()

    def _load_document_default(self) -> List[Document]:
        """Fetch URL document with trafilatura."""

        import re
        import unicodedata

        import requests
        from bs4 import BeautifulSoup

        def clean_text(text: str) -> str:
            """Clean text by removing special Unicode characters."""
            if not text:
                return ""

            # Remove zero-width characters and other invisible Unicode characters
            text = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", text)

            # Remove control characters except newline, tab, and carriage return
            text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]", "", text)

            # Normalize Unicode characters
            text = unicodedata.normalize("NFKC", text)

            # Clean up extra whitespace
            text = " ".join(text.split())

            return text.strip()

        try:
            # Set user agent to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit"
                "/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }

            # Fetch the webpage content
            response = requests.get(self._path, headers=headers, timeout=30)
            response.raise_for_status()

            # Determine encoding
            if self._encoding is not None:
                response.encoding = self._encoding
            elif response.encoding == "ISO-8859-1":
                response.encoding = response.apparent_encoding

            # Parse HTML content
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text content
            text_content = soup.get_text(strip=True)

            # Clean up whitespace
            lines = (line.strip() for line in text_content.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text_content = " ".join(chunk for chunk in chunks if chunk)
            text_content = clean_text(text_content)

            # Get page title if available
            title = (
                soup.title.string.strip() if soup.title and soup.title.string else ""
            )
            title = clean_text(title)

            description = soup.find("meta", attrs={"name": "description"})
            desc_content = description["content"] if description else ""
            desc_content = clean_text(desc_content)

            # Create metadata
            metadata = {
                "source": self._path,
                "title": title,
                "encoding": response.encoding,
                "description": desc_content,
            }

            document = Document(content=text_content, metadata=metadata)
            return [document]
        except Exception as e:
            raise ValueError(f"Failed to parse URL content: {str(e)}")

    @classmethod
    def support_chunk_strategy(cls) -> List[ChunkStrategy]:
        """Return support chunk strategy."""
        return [
            ChunkStrategy.CHUNK_BY_SIZE,
            ChunkStrategy.CHUNK_BY_SEPARATOR,
        ]

    @classmethod
    def default_chunk_strategy(cls) -> ChunkStrategy:
        """Return default chunk strategy."""
        return ChunkStrategy.CHUNK_BY_SIZE

    @classmethod
    def type(cls):
        """Return knowledge type."""
        return KnowledgeType.URL
