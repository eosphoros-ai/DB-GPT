"""Embedding retriever operator."""

from functools import reduce
from typing import List, Optional, Union

from dbgpt.core import Chunk
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.core.interface.operators.retriever import RetrieverOperator
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.i18n_utils import _

from ..assembler.embedding import EmbeddingAssembler
from ..chunk_manager import ChunkParameters
from ..knowledge import Knowledge
from ..retriever.embedding import EmbeddingRetriever
from ..retriever.rerank import Ranker
from ..retriever.rewrite import QueryRewrite
from .assembler import AssemblerOperator


class EmbeddingRetrieverOperator(RetrieverOperator[Union[str, List[str]], List[Chunk]]):
    """The Embedding Retriever Operator."""

    metadata = ViewMetadata(
        label=_("Embedding Retriever Operator"),
        name="embedding_retriever_operator",
        description=_("Retrieve candidates from vector store."),
        category=OperatorCategory.RAG,
        parameters=[
            Parameter.build_from(
                _("Vector Store Connector"),
                "vector_store_connector",
                VectorStoreConnector,
                description=_("The vector store connector."),
            ),
            Parameter.build_from(
                _("Top K"),
                "top_k",
                int,
                description=_("The number of candidates."),
            ),
            Parameter.build_from(
                _("Score Threshold"),
                "score_threshold",
                float,
                description=_(
                    "The score threshold, if score of candidate is less than it, it "
                    "will be filtered."
                ),
                optional=True,
                default=0.3,
            ),
            Parameter.build_from(
                _("Query Rewrite"),
                "query_rewrite",
                QueryRewrite,
                description=_("The query rewrite resource."),
                optional=True,
                default=None,
            ),
            Parameter.build_from(
                _("Rerank"),
                "rerank",
                Ranker,
                description=_("The rerank."),
                optional=True,
                default=None,
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Query"),
                "query",
                str,
                description=_("The query to retrieve."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Candidates"),
                "candidates",
                Chunk,
                description=_("The retrieved candidates."),
                is_list=True,
            )
        ],
    )

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        top_k: int,
        score_threshold: float = 0.3,
        query_rewrite: Optional[QueryRewrite] = None,
        rerank: Optional[Ranker] = None,
        **kwargs
    ):
        """Create a new EmbeddingRetrieverOperator."""
        super().__init__(**kwargs)
        self._score_threshold = score_threshold
        self._retriever = EmbeddingRetriever(
            vector_store_connector=vector_store_connector,
            top_k=top_k,
            query_rewrite=query_rewrite,
            rerank=rerank,
        )

    def retrieve(self, query: Union[str, List[str]]) -> List[Chunk]:
        """Retrieve the candidates."""
        if isinstance(query, str):
            return self._retriever.retrieve_with_scores(query, self._score_threshold)
        elif isinstance(query, list):
            candidates = [
                self._retriever.retrieve_with_scores(q, self._score_threshold)
                for q in query
            ]
            return reduce(lambda x, y: x + y, candidates)


class EmbeddingAssemblerOperator(AssemblerOperator[Knowledge, List[Chunk]]):
    """The Embedding Assembler Operator."""

    metadata = ViewMetadata(
        label=_("Embedding Assembler Operator"),
        name="embedding_assembler_operator",
        description=_("Load knowledge and assemble embedding chunks to vector store."),
        category=OperatorCategory.RAG,
        parameters=[
            Parameter.build_from(
                _("Vector Store Connector"),
                "vector_store_connector",
                VectorStoreConnector,
                description=_("The vector store connector."),
            ),
            Parameter.build_from(
                _("Chunk Parameters"),
                "chunk_parameters",
                ChunkParameters,
                description=_("The chunk parameters."),
                optional=True,
                default=None,
            ),
        ],
        inputs=[
            IOField.build_from(
                _("Knowledge"),
                "knowledge",
                Knowledge,
                description=_("The knowledge to be loaded."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Chunks"),
                "chunks",
                Chunk,
                description=_(
                    "The assembled chunks, it has been persisted to vector " "store."
                ),
                is_list=True,
            )
        ],
    )

    def __init__(
        self,
        vector_store_connector: VectorStoreConnector,
        chunk_parameters: Optional[ChunkParameters] = None,
        **kwargs
    ):
        """Create a new EmbeddingAssemblerOperator.

        Args:
            vector_store_connector (VectorStoreConnector): The vector store connector.
            chunk_parameters (Optional[ChunkParameters], optional): The chunk
                parameters. Defaults to ChunkParameters(chunk_strategy="CHUNK_BY_SIZE").
        """
        if not chunk_parameters:
            chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
        self._chunk_parameters = chunk_parameters
        self._vector_store_connector = vector_store_connector
        super().__init__(**kwargs)

    def assemble(self, knowledge: Knowledge) -> List[Chunk]:
        """Assemble knowledge for input value."""
        assembler = EmbeddingAssembler.load_from_knowledge(
            knowledge=knowledge,
            chunk_parameters=self._chunk_parameters,
            vector_store_connector=self._vector_store_connector,
        )
        assembler.persist()
        return assembler.get_chunks()
