"""Base schema for data structures."""
import json
import textwrap
import uuid
from abc import abstractmethod
from enum import Enum, auto
from hashlib import sha256
from typing import Any, Dict, List, Optional, Union

from langchain.schema import Document
from pydantic import BaseModel, Field, root_validator
from typing_extensions import Self


DEFAULT_TEXT_NODE_TMPL = "{metadata_str}\n\n{content}"
DEFAULT_METADATA_TMPL = "{key}: {value}"
# NOTE: for pretty printing
TRUNCATE_LENGTH = 350
WRAP_WIDTH = 70


class BaseComponent(BaseModel):
    """Base component object to caputure class names."""

    """reference llama-index"""

    @classmethod
    @abstractmethod
    def class_name(cls) -> str:
        """Get class name."""

    def to_dict(self, **kwargs: Any) -> Dict[str, Any]:
        data = self.dict(**kwargs)
        data["class_name"] = self.class_name()
        return data

    def to_json(self, **kwargs: Any) -> str:
        data = self.to_dict(**kwargs)
        return json.dumps(data)

    # TODO: return type here not supported by current mypy version
    @classmethod
    def from_dict(cls, data: Dict[str, Any], **kwargs: Any) -> Self:  # type: ignore
        if isinstance(kwargs, dict):
            data.update(kwargs)

        data.pop("class_name", None)
        return cls(**data)

    @classmethod
    def from_json(cls, data_str: str, **kwargs: Any) -> Self:  # type: ignore
        data = json.loads(data_str)
        return cls.from_dict(data, **kwargs)


class NodeRelationship(str, Enum):
    """Node relationships used in `BaseNode` class.

    Attributes:
        SOURCE: The node is the source document.
        PREVIOUS: The node is the previous node in the document.
        NEXT: The node is the next node in the document.
        PARENT: The node is the parent node in the document.
        CHILD: The node is a child node in the document.

    """

    SOURCE = auto()
    PREVIOUS = auto()
    NEXT = auto()
    PARENT = auto()
    CHILD = auto()


class ObjectType(str, Enum):
    TEXT = auto()
    IMAGE = auto()
    INDEX = auto()
    DOCUMENT = auto()


class MetadataMode(str, Enum):
    ALL = auto()
    EMBED = auto()
    LLM = auto()
    NONE = auto()


class RelatedNodeInfo(BaseComponent):
    node_id: str
    node_type: Optional[ObjectType] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    hash: Optional[str] = None

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "RelatedNodeInfo"


RelatedNodeType = Union[RelatedNodeInfo, List[RelatedNodeInfo]]


# Node classes for indexes
class BaseNode(BaseComponent):
    """Base node Object.

    Generic abstract interface for retrievable nodes

    """

    class Config:
        allow_population_by_field_name = True

    id_: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique ID of the node."
    )
    embedding: Optional[List[float]] = Field(
        default=None, description="Embedding of the node."
    )

    """"
    metadata fields
    - injected as part of the text shown to LLMs as context
    - injected as part of the text for generating embeddings
    - used by vector DBs for metadata filtering

    """
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="A flat dictionary of metadata fields",
        alias="extra_info",
    )
    excluded_embed_metadata_keys: List[str] = Field(
        default_factory=list,
        description="Metadata keys that are exluded from text for the embed model.",
    )
    excluded_llm_metadata_keys: List[str] = Field(
        default_factory=list,
        description="Metadata keys that are exluded from text for the LLM.",
    )
    relationships: Dict[NodeRelationship, RelatedNodeType] = Field(
        default_factory=dict,
        description="A mapping of relationships to other node information.",
    )
    hash: str = Field(default="", description="Hash of the node content.")

    @classmethod
    @abstractmethod
    def get_type(cls) -> str:
        """Get Object type."""

    @abstractmethod
    def get_content(self, metadata_mode: MetadataMode = MetadataMode.ALL) -> str:
        """Get object content."""

    @abstractmethod
    def get_metadata_str(self, mode: MetadataMode = MetadataMode.ALL) -> str:
        """Metadata string."""

    @abstractmethod
    def set_content(self, value: Any) -> None:
        """Set the content of the node."""

    @property
    def node_id(self) -> str:
        return self.id_

    @node_id.setter
    def node_id(self, value: str) -> None:
        self.id_ = value

    @property
    def source_node(self) -> Optional[RelatedNodeInfo]:
        """Source object node.

        Extracted from the relationships field.

        """
        if NodeRelationship.SOURCE not in self.relationships:
            return None

        relation = self.relationships[NodeRelationship.SOURCE]
        if isinstance(relation, list):
            raise ValueError("Source object must be a single RelatedNodeInfo object")
        return relation

    @property
    def prev_node(self) -> Optional[RelatedNodeInfo]:
        """Prev node."""
        if NodeRelationship.PREVIOUS not in self.relationships:
            return None

        relation = self.relationships[NodeRelationship.PREVIOUS]
        if not isinstance(relation, RelatedNodeInfo):
            raise ValueError("Previous object must be a single RelatedNodeInfo object")
        return relation

    @property
    def next_node(self) -> Optional[RelatedNodeInfo]:
        """Next node."""
        if NodeRelationship.NEXT not in self.relationships:
            return None

        relation = self.relationships[NodeRelationship.NEXT]
        if not isinstance(relation, RelatedNodeInfo):
            raise ValueError("Next object must be a single RelatedNodeInfo object")
        return relation

    @property
    def parent_node(self) -> Optional[RelatedNodeInfo]:
        """Parent node."""
        if NodeRelationship.PARENT not in self.relationships:
            return None

        relation = self.relationships[NodeRelationship.PARENT]
        if not isinstance(relation, RelatedNodeInfo):
            raise ValueError("Parent object must be a single RelatedNodeInfo object")
        return relation

    @property
    def child_nodes(self) -> Optional[List[RelatedNodeInfo]]:
        """Child nodes."""
        if NodeRelationship.CHILD not in self.relationships:
            return None

        relation = self.relationships[NodeRelationship.CHILD]
        if not isinstance(relation, list):
            raise ValueError("Child objects must be a list of RelatedNodeInfo objects.")
        return relation

    @property
    def ref_doc_id(self) -> Optional[str]:
        """Deprecated: Get ref doc id."""
        source_node = self.source_node
        if source_node is None:
            return None
        return source_node.node_id

    @property
    def extra_info(self) -> Dict[str, Any]:
        """TODO: DEPRECATED: Extra info."""
        return self.metadata

    def __str__(self) -> str:
        source_text_truncated = truncate_text(
            self.get_content().strip(), TRUNCATE_LENGTH
        )
        source_text_wrapped = textwrap.fill(
            f"Text: {source_text_truncated}\n", width=WRAP_WIDTH
        )
        return f"Node ID: {self.node_id}\n{source_text_wrapped}"

    def truncate_text(text: str, max_length: int) -> str:
        """Truncate text to a maximum length."""
        if len(text) <= max_length:
            return text
        return text[: max_length - 3] + "..."

    def get_embedding(self) -> List[float]:
        """Get embedding.

        Errors if embedding is None.

        """
        if self.embedding is None:
            raise ValueError("embedding not set.")
        return self.embedding

    def as_related_node_info(self) -> RelatedNodeInfo:
        """Get node as RelatedNodeInfo."""
        return RelatedNodeInfo(
            node_id=self.node_id, metadata=self.metadata, hash=self.hash
        )


class TextNode(BaseNode):
    text: str = Field(default="", description="Text content of the node.")
    start_char_idx: Optional[int] = Field(
        default=None, description="Start char index of the node."
    )
    end_char_idx: Optional[int] = Field(
        default=None, description="End char index of the node."
    )
    text_template: str = Field(
        default=DEFAULT_TEXT_NODE_TMPL,
        description=(
            "Template for how text is formatted, with {content} and "
            "{metadata_str} placeholders."
        ),
    )
    metadata_template: str = Field(
        default=DEFAULT_METADATA_TMPL,
        description=(
            "Template for how metadata is formatted, with {key} and "
            "{value} placeholders."
        ),
    )
    metadata_seperator: str = Field(
        default="\n",
        description="Seperator between metadata fields when converting to string.",
    )

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "TextNode"

    @root_validator
    def _check_hash(cls, values: dict) -> dict:
        """Generate a hash to represent the node."""
        text = values.get("text", "")
        metadata = values.get("metadata", {})
        doc_identity = str(text) + str(metadata)
        values["hash"] = str(
            sha256(doc_identity.encode("utf-8", "surrogatepass")).hexdigest()
        )
        return values

    @classmethod
    def get_type(cls) -> str:
        """Get Object type."""
        return ObjectType.TEXT

    def get_content(self, metadata_mode: MetadataMode = MetadataMode.NONE) -> str:
        """Get object content."""
        metadata_str = self.get_metadata_str(mode=metadata_mode).strip()
        if not metadata_str:
            return self.text

        return self.text_template.format(
            content=self.text, metadata_str=metadata_str
        ).strip()

    def get_metadata_str(self, mode: MetadataMode = MetadataMode.ALL) -> str:
        """metadata info string."""
        if mode == MetadataMode.NONE:
            return ""

        usable_metadata_keys = set(self.metadata.keys())
        if mode == MetadataMode.LLM:
            for key in self.excluded_llm_metadata_keys:
                if key in usable_metadata_keys:
                    usable_metadata_keys.remove(key)
        elif mode == MetadataMode.EMBED:
            for key in self.excluded_embed_metadata_keys:
                if key in usable_metadata_keys:
                    usable_metadata_keys.remove(key)

        return self.metadata_seperator.join(
            [
                self.metadata_template.format(key=key, value=str(value))
                for key, value in self.metadata.items()
                if key in usable_metadata_keys
            ]
        )

    def set_content(self, value: str) -> None:
        """Set the content of the node."""
        self.text = value

    def get_node_info(self) -> Dict[str, Any]:
        """Get node info."""
        return {"start": self.start_char_idx, "end": self.end_char_idx}

    def get_text(self) -> str:
        return self.get_content(metadata_mode=MetadataMode.NONE)

    @property
    def node_info(self) -> Dict[str, Any]:
        """Deprecated: Get node info."""
        return self.get_node_info()


# TODO: legacy backport of old Node class
Node = TextNode


class ImageNode(TextNode):
    """Node with image."""

    # TODO: store reference instead of actual image
    # base64 encoded image str
    image: Optional[str] = None

    @classmethod
    def get_type(cls) -> str:
        return ObjectType.IMAGE

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "ImageNode"


class IndexNode(TextNode):
    """Node with reference to any object.

    This can include other indices, query engines, retrievers.

    This can also include other nodes (though this is overlapping with `relationships`
    on the Node class).

    """

    index_id: str

    @classmethod
    def from_text_node(
        cls,
        node: TextNode,
        index_id: str,
    ) -> "IndexNode":
        """Create index node from text node."""
        # copy all attributes from text node, add index id
        return cls(
            **node.dict(),
            index_id=index_id,
        )

    @classmethod
    def get_type(cls) -> str:
        return ObjectType.INDEX

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "IndexNode"


class NodeWithScore(BaseComponent):
    node: BaseNode
    score: Optional[float] = None

    def __str__(self) -> str:
        return f"{self.node}\nScore: {self.score: 0.3f}\n"

    def get_score(self, raise_error: bool = False) -> float:
        """Get score."""
        if self.score is None:
            if raise_error:
                raise ValueError("Score not set.")
            else:
                return 0.0
        else:
            return self.score

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "NodeWithScore"

    ##### pass through methods to BaseNode #####
    @property
    def node_id(self) -> str:
        return self.node.node_id

    @property
    def id_(self) -> str:
        return self.node.id_

    @property
    def text(self) -> str:
        if isinstance(self.node, TextNode):
            return self.node.text
        else:
            raise ValueError("Node must be a TextNode to get text.")

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.node.metadata

    @property
    def embedding(self) -> Optional[List[float]]:
        return self.node.embedding

    def get_text(self) -> str:
        if isinstance(self.node, TextNode):
            return self.node.get_text()
        else:
            raise ValueError("Node must be a TextNode to get text.")

    def get_content(self, metadata_mode: MetadataMode = MetadataMode.NONE) -> str:
        return self.node.get_content(metadata_mode=metadata_mode)

    def get_embedding(self) -> List[float]:
        return self.node.get_embedding()


# Document Classes for Readers


class Document(TextNode):
    """Generic interface for a data document.

    This document connects to data sources.

    """

    # TODO: A lot of backwards compatibility logic here, clean up
    id_: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID of the node.",
        alias="doc_id",
    )

    _compat_fields = {"doc_id": "id_", "extra_info": "metadata"}

    @classmethod
    def get_type(cls) -> str:
        """Get Document type."""
        return ObjectType.DOCUMENT

    @property
    def doc_id(self) -> str:
        """Get document ID."""
        return self.id_

    def __str__(self) -> str:
        source_text_truncated = truncate_text(
            self.get_content().strip(), TRUNCATE_LENGTH
        )
        source_text_wrapped = textwrap.fill(
            f"Text: {source_text_truncated}\n", width=WRAP_WIDTH
        )
        return f"Doc ID: {self.doc_id}\n{source_text_wrapped}"

    def get_doc_id(self) -> str:
        """TODO: Deprecated: Get document ID."""
        return self.id_

    def __setattr__(self, name: str, value: object) -> None:
        if name in self._compat_fields:
            name = self._compat_fields[name]
        super().__setattr__(name, value)

    def to_langchain_format(self) -> Document:
        """Convert struct to LangChain document format."""
        metadata = self.metadata or {}
        return Document(page_content=self.text, metadata=metadata)

    @classmethod
    def from_langchain_format(cls, doc: Document) -> "Document":
        """Convert struct from LangChain document format."""
        return cls(text=doc.page_content, metadata=doc.metadata)

    @classmethod
    def example(cls) -> "Document":
        document = Document(
            text="",
            metadata={"filename": "README.md", "category": "codebase"},
        )
        return document

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "Document"


class ImageDocument(Document):
    """Data document containing an image."""

    # base64 encoded image str
    image: Optional[str] = None

    @classmethod
    def class_name(cls) -> str:
        """Get class name."""
        return "ImageDocument"
