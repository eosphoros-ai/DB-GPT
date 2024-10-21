"""Chunk document schema."""

import json
import uuid
from typing import Any, Dict, Optional

from dbgpt._private.pydantic import BaseModel, Field, model_to_dict


class Document(BaseModel):
    """Document including document content, document metadata."""

    content: str = Field(default="", description="document text content")

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="metadata fields",
    )

    def set_content(self, content: str) -> None:
        """Set document content."""
        self.content = content

    def get_content(self) -> str:
        """Get document content."""
        return self.content

    @classmethod
    def langchain2doc(cls, document):
        """Transform Langchain to Document format."""
        metadata = document.metadata or {}
        return cls(content=document.page_content, metadata=metadata)

    @classmethod
    def doc2langchain(cls, chunk):
        """Transform Document to Langchain format."""
        from langchain.schema import Document as LCDocument

        return LCDocument(page_content=chunk.content, metadata=chunk.metadata)


class Chunk(Document):
    """The chunk document schema.

    Document Chunk including chunk content, chunk metadata, chunk summary, chunk
    relations.
    """

    chunk_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="unique id for the chunk"
    )
    chunk_name: str = Field(default="", description="chunk name")
    content: str = Field(default="", description="chunk text content")

    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="metadata fields",
    )
    score: float = Field(default=0.0, description="chunk text similarity score")
    summary: str = Field(default="", description="chunk text summary")
    separator: str = Field(
        default="\n",
        description="Separator between metadata fields when converting to string.",
    )
    retriever: Optional[str] = Field(default=None, description="retriever name")

    def to_dict(self, **kwargs: Any) -> Dict[str, Any]:
        """Convert Chunk to dict."""
        data = model_to_dict(self, **kwargs)
        data["class_name"] = self.class_name()
        return data

    def to_json(self, **kwargs: Any) -> str:
        """Convert Chunk to json."""
        data = self.to_dict(**kwargs)
        return json.dumps(data)

    def __hash__(self):
        """Hash function."""
        return hash((self.chunk_id,))

    def __eq__(self, other):
        """Equal function."""
        return self.chunk_id == other.chunk_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs: Any):  # type: ignore
        """Create Chunk from dict."""
        if isinstance(kwargs, dict):
            data.update(kwargs)

        data.pop("class_name", None)
        return cls(**data)

    @classmethod
    def from_json(cls, data_str: str, **kwargs: Any):  # type: ignore
        """Create Chunk from json."""
        data = json.loads(data_str)
        return cls.from_dict(data, **kwargs)

    @classmethod
    def langchain2chunk(cls, document):
        """Transform Langchain to Chunk format."""
        metadata = document.metadata or {}
        return cls(content=document.page_content, metadata=metadata)

    @classmethod
    def llamaindex2chunk(cls, node):
        """Transform llama-index to Chunk format."""
        metadata = node.metadata or {}
        return cls(content=node.content, metadata=metadata)

    @classmethod
    def chunk2langchain(cls, chunk):
        """Transform Chunk to Langchain format."""
        try:
            from langchain.schema import Document as LCDocument  # mypy: ignore
        except ImportError:
            raise ValueError(
                "Could not import python package: langchain "
                "Please install langchain by command `pip install langchain"
            )
        return LCDocument(page_content=chunk.content, metadata=chunk.metadata)

    @classmethod
    def chunk2llamaindex(cls, chunk):
        """Transform Chunk to llama-index format."""
        try:
            from llama_index.schema import TextNode
        except ImportError:
            raise ValueError(
                "Could not import python package: llama_index "
                "Please install llama_index by command `pip install llama_index"
            )
        return TextNode(text=chunk.content, metadata=chunk.metadata)
