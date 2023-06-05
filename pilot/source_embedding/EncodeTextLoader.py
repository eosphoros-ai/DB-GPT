from typing import List, Optional
import chardet

from langchain.docstore.document import Document
from langchain.document_loaders.base import BaseLoader


class EncodeTextLoader(BaseLoader):
    """Load text files."""

    def __init__(self, file_path: str, encoding: Optional[str] = None):
        """Initialize with file path."""
        self.file_path = file_path
        self.encoding = encoding

    def load(self) -> List[Document]:
        """Load from file path."""
        with open(self.file_path, "rb") as f:
            raw_text = f.read()
            result = chardet.detect(raw_text)
            if result["encoding"] is None:
                text = raw_text.decode("utf-8")
            else:
                text = raw_text.decode(result["encoding"])
        metadata = {"source": self.file_path}
        return [Document(page_content=text, metadata=metadata)]
