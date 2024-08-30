from typing import List, Optional

from dbgpt._private.config import Config
from dbgpt.core import Chunk
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import (
    TAGS_ORDER_HIGH,
    FunctionDynamicOptions,
    IOField,
    OperatorCategory,
    OptionValue,
    Parameter,
    ViewMetadata,
    ui,
)
from dbgpt.serve.rag.retriever.knowledge_space import KnowledgeSpaceRetriever
from dbgpt.util.i18n_utils import _

from .llm import HOContextBody

CFG = Config()


def _load_space_name() -> List[OptionValue]:
    from dbgpt.serve.rag.models.models import KnowledgeSpaceDao, KnowledgeSpaceEntity

    spaces = KnowledgeSpaceDao().get_knowledge_space(KnowledgeSpaceEntity())
    return [
        OptionValue(label=space.name, name=space.name, value=space.name)
        for space in spaces
    ]


_PARAMETER_CONTEXT_KEY = Parameter.build_from(
    _("Context Key"),
    "context",
    type=str,
    optional=True,
    default="context",
    description=_("The key of the context, it will be used in building the prompt"),
)
_PARAMETER_TOP_K = Parameter.build_from(
    _("Top K"),
    "top_k",
    type=int,
    optional=True,
    default=5,
    description=_("The number of chunks to retrieve"),
)
_PARAMETER_SCORE_THRESHOLD = Parameter.build_from(
    _("Minimum Match Score"),
    "score_threshold",
    type=float,
    optional=True,
    default=0.3,
    description=_(
        _(
            "The minimum match score for the retrieved chunks, it will be dropped if "
            "the match score is less than the threshold"
        )
    ),
    ui=ui.UISlider(attr=ui.UISlider.UIAttribute(min=0.0, max=1.0, step=0.1)),
)

_PARAMETER_RE_RANKER_ENABLED = Parameter.build_from(
    _("Reranker Enabled"),
    "reranker_enabled",
    type=bool,
    optional=True,
    default=None,
    description=_("Whether to enable the reranker"),
)
_PARAMETER_RE_RANKER_TOP_K = Parameter.build_from(
    _("Reranker Top K"),
    "reranker_top_k",
    type=int,
    optional=True,
    default=3,
    description=_("The top k for the reranker"),
)

_INPUTS_QUESTION = IOField.build_from(
    _("User question"),
    "query",
    str,
    description=_("The user question to retrieve the knowledge"),
)
_OUTPUTS_CONTEXT = IOField.build_from(
    _("Retrieved context"),
    "context",
    HOContextBody,
    description=_("The retrieved context from the knowledge space"),
)


class HOKnowledgeOperator(MapOperator[str, HOContextBody]):
    _share_data_key = "_higher_order_knowledge_operator_retriever_chunks"

    class ChunkMapper(MapOperator[HOContextBody, List[Chunk]]):
        async def map(self, context: HOContextBody) -> List[Chunk]:
            chunks = await self.current_dag_context.get_from_share_data(
                HOKnowledgeOperator._share_data_key
            )
            return chunks

    metadata = ViewMetadata(
        label=_("Knowledge Operator"),
        name="higher_order_knowledge_operator",
        category=OperatorCategory.RAG,
        description=_(
            _(
                "Knowledge Operator, retrieve your knowledge(documents) from knowledge"
                " space"
            )
        ),
        parameters=[
            Parameter.build_from(
                _("Knowledge Space Name"),
                "knowledge_space",
                type=str,
                options=FunctionDynamicOptions(func=_load_space_name),
                description=_("The name of the knowledge space"),
            ),
            _PARAMETER_CONTEXT_KEY.new(),
            _PARAMETER_TOP_K.new(),
            _PARAMETER_SCORE_THRESHOLD.new(),
            _PARAMETER_RE_RANKER_ENABLED.new(),
            _PARAMETER_RE_RANKER_TOP_K.new(),
        ],
        inputs=[
            _INPUTS_QUESTION.new(),
        ],
        outputs=[
            _OUTPUTS_CONTEXT.new(),
            IOField.build_from(
                _("Chunks"),
                "chunks",
                Chunk,
                is_list=True,
                description=_("The retrieved chunks from the knowledge space"),
                mappers=[ChunkMapper],
            ),
        ],
        tags={"order": TAGS_ORDER_HIGH},
    )

    def __init__(
        self,
        knowledge_space: str,
        context_key: Optional[str] = "context",
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        reranker_enabled: Optional[bool] = None,
        reranker_top_k: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._knowledge_space = knowledge_space
        self._context_key = context_key
        self._top_k = top_k
        self._score_threshold = score_threshold
        self._reranker_enabled = reranker_enabled
        self._reranker_top_k = reranker_top_k

        from dbgpt.rag.embedding.embedding_factory import RerankEmbeddingFactory
        from dbgpt.rag.retriever.rerank import RerankEmbeddingsRanker
        from dbgpt.serve.rag.models.models import (
            KnowledgeSpaceDao,
            KnowledgeSpaceEntity,
        )

        spaces = KnowledgeSpaceDao().get_knowledge_space(
            KnowledgeSpaceEntity(name=knowledge_space)
        )
        if len(spaces) != 1:
            raise Exception(f"invalid space name: {knowledge_space}")
        space = spaces[0]

        reranker: Optional[RerankEmbeddingsRanker] = None

        if CFG.RERANK_MODEL and self._reranker_enabled:
            reranker_top_k = (
                self._reranker_top_k
                if self._reranker_top_k is not None
                else CFG.RERANK_TOP_K
            )
            rerank_embeddings = RerankEmbeddingFactory.get_instance(
                CFG.SYSTEM_APP
            ).create()
            reranker = RerankEmbeddingsRanker(rerank_embeddings, topk=reranker_top_k)
            if self._top_k < reranker_top_k or self._top_k < 20:
                # We use reranker, so if the top_k is less than 20,
                # we need to set it to 20
                self._top_k = max(reranker_top_k, 20)

        self._space_retriever = KnowledgeSpaceRetriever(
            space_id=space.id,
            top_k=self._top_k,
            rerank=reranker,
        )

    async def map(self, query: str) -> HOContextBody:
        chunks = await self._space_retriever.aretrieve_with_scores(
            query, self._score_threshold
        )
        await self.current_dag_context.save_to_share_data(self._share_data_key, chunks)
        return HOContextBody(
            context_key=self._context_key,
            context=[chunk.content for chunk in chunks],
        )
