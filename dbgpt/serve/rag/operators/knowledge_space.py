from functools import reduce
from typing import List, Optional

from dbgpt.app.knowledge.api import knowledge_space_service
from dbgpt.app.knowledge.request.request import KnowledgeSpaceRequest
from dbgpt.app.knowledge.service import CFG, KnowledgeService
from dbgpt.configs.model_config import EMBEDDING_MODEL_CONFIG
from dbgpt.core import (
    BaseMessage,
    ChatPromptTemplate,
    HumanPromptTemplate,
    ModelMessage,
)
from dbgpt.core.awel import JoinOperator, MapOperator
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    OperatorType,
    OptionValue,
    Parameter,
    ViewMetadata,
)
from dbgpt.core.awel.task.base import IN, OUT
from dbgpt.core.interface.operators.prompt_operator import BasePromptBuilderOperator
from dbgpt.rag.embedding.embedding_factory import EmbeddingFactory
from dbgpt.rag.retriever.embedding import EmbeddingRetriever
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector
from dbgpt.util.function_utils import rearrange_args_by_type


class SpaceRetrieverOperator(MapOperator[IN, OUT]):
    """knowledge space retriever operator."""

    metadata = ViewMetadata(
        label="Knowledge Space Operator",
        name="space_operator",
        category=OperatorCategory.RAG,
        description="knowledge space retriever operator.",
        inputs=[IOField.build_from("query", "query", str, "user query")],
        outputs=[
            IOField.build_from(
                "related chunk content",
                "related chunk content",
                List,
                description="related chunk content",
            )
        ],
        parameters=[
            Parameter.build_from(
                "Space Name",
                "space_name",
                str,
                options=[
                    OptionValue(label=space.name, name=space.name, value=space.name)
                    for space in knowledge_space_service.get_knowledge_space(
                        KnowledgeSpaceRequest()
                    )
                ],
                optional=False,
                default=None,
                description="space name.",
            )
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(self, space_name: str, recall_score: Optional[float] = 0.3, **kwargs):
        """
        Args:
            space_name (str): The space name.
            recall_score (Optional[float], optional): The recall score. Defaults to 0.3.
        """
        self._space_name = space_name
        self._recall_score = recall_score
        self._service = KnowledgeService()
        embedding_factory = CFG.SYSTEM_APP.get_component(
            "embedding_factory", EmbeddingFactory
        )
        embedding_fn = embedding_factory.create(
            model_name=EMBEDDING_MODEL_CONFIG[CFG.EMBEDDING_MODEL]
        )
        config = VectorStoreConfig(name=self._space_name, embedding_fn=embedding_fn)
        self._vector_store_connector = VectorStoreConnector(
            vector_store_type=CFG.VECTOR_STORE_TYPE,
            vector_store_config=config,
        )

        super().__init__(**kwargs)

    async def map(self, query: IN) -> OUT:
        """Map input value to output value.

        Args:
            input_value (IN): The input value.

        Returns:
            OUT: The output value.
        """
        space_context = self._service.get_space_context(self._space_name)
        top_k = (
            CFG.KNOWLEDGE_SEARCH_TOP_SIZE
            if space_context is None
            else int(space_context["embedding"]["topk"])
        )
        recall_score = (
            CFG.KNOWLEDGE_SEARCH_RECALL_SCORE
            if space_context is None
            else float(space_context["embedding"]["recall_score"])
        )
        embedding_retriever = EmbeddingRetriever(
            top_k=top_k,
            vector_store_connector=self._vector_store_connector,
        )
        if isinstance(query, str):
            candidates = await embedding_retriever.aretrieve_with_scores(
                query, recall_score
            )
        elif isinstance(query, list):
            candidates = [
                await embedding_retriever.aretrieve_with_scores(q, recall_score)
                for q in query
            ]
            candidates = reduce(lambda x, y: x + y, candidates)
        return [candidate.content for candidate in candidates]


class KnowledgeSpacePromptBuilderOperator(
    BasePromptBuilderOperator, JoinOperator[List[ModelMessage]]
):
    """The operator to build the prompt with static prompt.

    The prompt will pass to this operator.
    """

    metadata = ViewMetadata(
        label="Knowledge Space Prompt Builder Operator",
        name="knowledge_space_prompt_builder_operator",
        description="Build messages from prompt template and chat history.",
        operator_type=OperatorType.JOIN,
        category=OperatorCategory.CONVERSION,
        parameters=[
            Parameter.build_from(
                "Chat Prompt Template",
                "prompt",
                ChatPromptTemplate,
                description="The chat prompt template.",
            ),
            Parameter.build_from(
                "History Key",
                "history_key",
                str,
                optional=True,
                default="chat_history",
                description="The key of history in prompt dict.",
            ),
            Parameter.build_from(
                "String History",
                "str_history",
                bool,
                optional=True,
                default=False,
                description="Whether to convert the history to string.",
            ),
        ],
        inputs=[
            IOField.build_from(
                "user input",
                "user_input",
                str,
                is_list=False,
                description="user input",
            ),
            IOField.build_from(
                "space related context",
                "related_context",
                List,
                is_list=False,
                description="context of knowledge space.",
            ),
            IOField.build_from(
                "History",
                "history",
                BaseMessage,
                is_list=True,
                description="The history.",
            ),
        ],
        outputs=[
            IOField.build_from(
                "Formatted Messages",
                "formatted_messages",
                ModelMessage,
                is_list=True,
                description="The formatted messages.",
            )
        ],
    )

    def __init__(
        self,
        prompt: ChatPromptTemplate,
        history_key: str = "chat_history",
        check_storage: bool = True,
        str_history: bool = False,
        **kwargs,
    ):
        """Create a new history dynamic prompt builder operator.
        Args:

            prompt (ChatPromptTemplate): The chat prompt template.
            history_key (str, optional): The key of history in prompt dict. Defaults to "chat_history".
            check_storage (bool, optional): Whether to check the storage. Defaults to True.
            str_history (bool, optional): Whether to convert the history to string. Defaults to False.
        """

        self._prompt = prompt
        self._history_key = history_key
        self._str_history = str_history
        BasePromptBuilderOperator.__init__(self, check_storage=check_storage)
        JoinOperator.__init__(self, combine_function=self.merge_context, **kwargs)

    @rearrange_args_by_type
    async def merge_context(
        self,
        user_input: str,
        related_context: List[str],
        history: Optional[List[BaseMessage]],
    ) -> List[ModelMessage]:
        """Merge the prompt and history."""
        prompt_dict = dict()
        prompt_dict["context"] = related_context
        for prompt in self._prompt.messages:
            if isinstance(prompt, HumanPromptTemplate):
                prompt_dict[prompt.input_variables[0]] = user_input

        if history:
            if self._str_history:
                prompt_dict[self._history_key] = BaseMessage.messages_to_string(history)
            else:
                prompt_dict[self._history_key] = history
        return await self.format_prompt(self._prompt, prompt_dict)
