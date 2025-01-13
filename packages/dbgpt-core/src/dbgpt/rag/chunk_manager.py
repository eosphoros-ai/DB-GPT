"""Module for ChunkManager."""

from enum import Enum
from typing import Any, List, Optional

from dbgpt._private.pydantic import BaseModel, Field
from dbgpt.core import Chunk, Document
from dbgpt.core.awel.flow import Parameter, ResourceCategory, register_resource
from dbgpt.rag.extractor.base import Extractor
from dbgpt.rag.knowledge.base import ChunkStrategy, Knowledge
from dbgpt.rag.text_splitter import TextSplitter
from dbgpt.util.i18n_utils import _


class SplitterType(str, Enum):
    """The type of splitter."""

    LANGCHAIN = "langchain"
    LLAMA_INDEX = "llama-index"
    USER_DEFINE = "user_define"


@register_resource(
    _("Chunk Parameters"),
    "chunk_parameters",
    category=ResourceCategory.RAG,
    parameters=[
        Parameter.build_from(
            _("Chunk Strategy"),
            "chunk_strategy",
            str,
            description=_("chunk strategy"),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("Text Splitter"),
            "text_splitter",
            TextSplitter,
            description=_(
                "Text splitter, if not set, will use the default text splitter."
            ),
            optional=True,
            default=None,
        ),
        Parameter.build_from(
            _("Splitter Type"),
            "splitter_type",
            str,
            description=_("Splitter type"),
            optional=True,
            default=SplitterType.USER_DEFINE.value,
        ),
        Parameter.build_from(
            _("Chunk Size"),
            "chunk_size",
            int,
            description=_("Chunk size"),
            optional=True,
            default=512,
        ),
        Parameter.build_from(
            _("Chunk Overlap"),
            "chunk_overlap",
            int,
            description="Chunk overlap",
            optional=True,
            default=50,
        ),
        Parameter.build_from(
            _("Separator"),
            "separator",
            str,
            description=_("Chunk separator"),
            optional=True,
            default="\n",
        ),
        Parameter.build_from(
            _("Enable Merge"),
            "enable_merge",
            bool,
            description=_("Enable chunk merge by chunk_size."),
            optional=True,
            default=False,
        ),
    ],
)
class ChunkParameters(BaseModel):
    """The parameters for chunking."""

    chunk_strategy: str = Field(
        default=None,
        description="chunk strategy",
    )
    text_splitter: Optional[Any] = Field(
        default=None,
        description="text splitter",
    )

    splitter_type: SplitterType = Field(
        default=SplitterType.USER_DEFINE,
        description="splitter type",
    )

    chunk_size: int = Field(
        default=512,
        description="chunk size",
    )
    chunk_overlap: int = Field(
        default=50,
        description="chunk overlap",
    )
    separator: str = Field(
        default="\n",
        description="chunk separator",
    )
    enable_merge: bool = Field(
        default=None,
        description="enable chunk merge by chunk_size.",
    )


class ChunkManager:
    """Manager for chunks."""

    def __init__(
        self,
        knowledge: Knowledge,
        chunk_parameter: Optional[ChunkParameters] = None,
        extractor: Optional[Extractor] = None,
    ):
        """Create a new ChunkManager with the given knowledge.

        Args:
            knowledge: (Knowledge) Knowledge datasource.
            chunk_parameter: (Optional[ChunkParameter]) Chunk parameter.
            extractor: (Optional[Extractor]) Extractor to use for summarization.
        """
        self._knowledge = knowledge

        self._extractor = extractor
        self._chunk_parameters = chunk_parameter or ChunkParameters()
        self._chunk_strategy = (
            chunk_parameter.chunk_strategy
            if chunk_parameter and chunk_parameter.chunk_strategy
            else self._knowledge.default_chunk_strategy().name
        )
        self._text_splitter = self._chunk_parameters.text_splitter
        self._splitter_type = self._chunk_parameters.splitter_type

    def split(self, documents: List[Document]) -> List[Chunk]:
        """Split a document into chunks."""
        text_splitter = self._select_text_splitter()
        if SplitterType.LANGCHAIN == self._splitter_type:
            documents = text_splitter.split_documents(documents)
            return [Chunk.langchain2chunk(document) for document in documents]
        elif SplitterType.LLAMA_INDEX == self._splitter_type:
            nodes = text_splitter.split_documents(documents)
            return [Chunk.llamaindex2chunk(node) for node in nodes]
        else:
            return text_splitter.split_documents(documents)

    def split_with_summary(
        self, document: Any, chunk_strategy: ChunkStrategy
    ) -> List[Chunk]:
        """Split a document into chunks and summary."""
        raise NotImplementedError

    def extract(self, chunks: List[Chunk]) -> None:
        """Extract metadata from chunks."""
        if self._extractor:
            self._extractor.extract(chunks)

    @property
    def chunk_parameters(self) -> ChunkParameters:
        """Get chunk parameters."""
        return self._chunk_parameters

    def set_text_splitter(
        self,
        text_splitter: TextSplitter,
        splitter_type: SplitterType = SplitterType.LANGCHAIN,
    ) -> None:
        """Add text splitter."""
        self._text_splitter = text_splitter
        self._splitter_type = splitter_type

    def get_text_splitter(
        self,
    ) -> TextSplitter:
        """Return text splitter."""
        return self._select_text_splitter()

    def _select_text_splitter(
        self,
    ) -> TextSplitter:
        """Select text splitter by chunk strategy."""
        if self._text_splitter:
            return self._text_splitter
        if not self._chunk_strategy or self._chunk_strategy == "Automatic":
            self._chunk_strategy = self._knowledge.default_chunk_strategy().name
        if self._chunk_strategy not in [
            support_chunk_strategy.name
            for support_chunk_strategy in self._knowledge.support_chunk_strategy()
        ]:
            current_type = self._knowledge.type().value
            if self._knowledge.document_type():
                current_type = self._knowledge.document_type().value
            raise ValueError(
                f"{current_type} knowledge not supported chunk strategy "
                f"{self._chunk_strategy} "
            )
        strategy = ChunkStrategy[self._chunk_strategy]
        return strategy.match(
            chunk_size=self._chunk_parameters.chunk_size,
            chunk_overlap=self._chunk_parameters.chunk_overlap,
            separator=self._chunk_parameters.separator,
            enable_merge=self._chunk_parameters.enable_merge,
        )
