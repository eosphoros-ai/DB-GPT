import json
import uuid
from typing import Any, Dict

from pydantic import Field, BaseModel


class Document(BaseModel):
    """Document including document content, document metadata."""

    content: str = (Field(default="", description="document text content"),)

    metadata: Dict[str, Any] = (
        Field(
            default_factory=dict,
            description="metadata fields",
        ),
    )

    def set_content(self, content: str) -> None:
        """Set the content"""
        self.content = content

    def get_content(self) -> str:
        return self.content

    @classmethod
    def langchain2doc(cls, document):
        """Transformation from Langchain to Chunk Document format."""
        metadata = document.metadata or {}
        return cls(content=document.page_content, metadata=metadata)

    @classmethod
    def doc2langchain(cls, chunk):
        """Transformation from Chunk to Langchain Document format."""
        from langchain.schema import Document as LCDocument

        return LCDocument(page_content=chunk.content, metadata=chunk.metadata)


class Chunk(Document):
    """
    Document Chunk including chunk content, chunk metadata, chunk summary, chunk relations.
    """

    chunk_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="unique id for the chunk"
    )
    content: str = Field(default="", description="chunk text content")

    metadata: Dict[str, Any] = (
        Field(
            default_factory=dict,
            description="metadata fields",
        ),
    )
    score: float = Field(default=0.0, description="chunk text similarity score")
    summary: str = Field(default="", description="chunk text summary")
    separator: str = Field(
        default="\n",
        description="Separator between metadata fields when converting to string.",
    )

    def to_dict(self, **kwargs: Any) -> Dict[str, Any]:
        data = self.dict(**kwargs)
        data["class_name"] = self.class_name()
        return data

    def to_json(self, **kwargs: Any) -> str:
        data = self.to_dict(**kwargs)
        return json.dumps(data)

    def __hash__(self):
        return hash((self.chunk_id,))

    def __eq__(self, other):
        return self.chunk_id == other.chunk_id

    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs: Any):  # type: ignore
        if isinstance(kwargs, dict):
            data.update(kwargs)

        data.pop("class_name", None)
        return cls(**data)

    @classmethod
    def from_json(cls, data_str: str, **kwargs: Any):  # type: ignore
        data = json.loads(data_str)
        return cls.from_dict(data, **kwargs)

    @classmethod
    def langchain2chunk(cls, document):
        """Transformation from Langchain to Chunk Document format."""
        metadata = document.metadata or {}
        return cls(content=document.page_content, metadata=document.metadata)

    @classmethod
    def llamaindex2chunk(cls, node):
        """Transformation from LLama-Index to Chunk Document format."""
        metadata = node.metadata or {}
        return cls(content=node.content, metadata=metadata)

    @classmethod
    def chunk2langchain(cls, chunk):
        """Transformation from Chunk to Langchain Document format."""
        from langchain.schema import Document as LCDocument

        return LCDocument(page_content=chunk.content, metadata=chunk.metadata)

    @classmethod
    def chunk2llamaindex(cls, chunk):
        """Transformation from Chunk to LLama-Index Document format."""
        from llama_index.schema import TextNode

        return TextNode(text=chunk.content, metadata=chunk.metadata)
