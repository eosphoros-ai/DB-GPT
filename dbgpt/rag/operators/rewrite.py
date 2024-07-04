"""The rewrite operator."""

from typing import Any, List, Optional

from dbgpt.core import LLMClient, ModelRequest
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import IOField, OperatorCategory, Parameter, ViewMetadata
from dbgpt.rag.extractor.fin_report import FinReportIntent
from dbgpt.rag.retriever.rewrite import QueryRewrite
from dbgpt.util.i18n_utils import _


class QueryRewriteOperator(MapOperator[dict, Any]):
    """The Rewrite Operator."""

    metadata = ViewMetadata(
        label=_("Query Rewrite Operator"),
        name="query_rewrite_operator",
        category=OperatorCategory.RAG,
        description=_("Query rewrite operator."),
        inputs=[
            IOField.build_from(
                _("Query context"), "query_context", dict, _("query context")
            )
        ],
        outputs=[
            IOField.build_from(
                _("Rewritten queries"),
                "queries",
                str,
                is_list=True,
                description=_("Rewritten queries"),
            )
        ],
        parameters=[
            Parameter.build_from(
                _("LLM Client"),
                "llm_client",
                LLMClient,
                description=_("The LLM Client."),
            ),
            Parameter.build_from(
                label=_("Model name"),
                name="model_name",
                type=str,
                optional=True,
                default="gpt-3.5-turbo",
                description=_("LLM model name."),
            ),
            Parameter.build_from(
                label=_("Prompt language"),
                name="language",
                type=str,
                optional=True,
                default="en",
                description=_("Prompt language."),
            ),
            Parameter.build_from(
                label=_("Number of results"),
                name="nums",
                type=int,
                optional=True,
                default=5,
                description=_("rewrite query number."),
            ),
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(
        self,
        llm_client: LLMClient,
        model_name: str = "gpt-3.5-turbo",
        language: Optional[str] = "en",
        nums: Optional[int] = 1,
        **kwargs
    ):
        """Init the query rewrite operator.

        Args:
            llm_client (Optional[LLMClient]): The LLM client.
            model_name (Optional[str]): The model name.
            language (Optional[str]): The prompt language.
            nums (Optional[int]): The number of the rewrite results.
        """
        super().__init__(**kwargs)
        self._nums = nums
        self._rewrite = QueryRewrite(
            llm_client=llm_client,
            model_name=model_name,
            language=language,
        )

    async def map(self, query_context: dict) -> List[str]:
        """Rewrite the query."""
        query = query_context.get("query")
        context = query_context.get("context")
        if not query:
            raise ValueError("query is required")
        return await self._rewrite.rewrite(
            origin_query=query, context=context, nums=self._nums
        )


class FinQueryRewriteOperator(MapOperator[ModelRequest, ModelRequest]):
    """The Rewrite Operator."""

    def __init__(
        self, intent: FinReportIntent = None, nums: Optional[int] = 1, **kwargs
    ):
        """Init the query rewrite operator.

        Args:
            llm_client (Optional[LLMClient]): The LLM client.
            model_name (Optional[str]): The model name.
            language (Optional[str]): The prompt language.
            nums (Optional[int]): The number of the rewrite results.
        """
        super().__init__(**kwargs)
        if not intent:
            raise ValueError("intent is required")
        self._intent: FinReportIntent = intent
        self._nums = nums

    async def map(self, request: ModelRequest) -> ModelRequest:
        """Rewrite the query."""
        if not request.messages:
            raise ValueError("messages is required")
        raw_query = request.messages[0].text
        # context = query_context.get("context")
        if not raw_query:
            raise ValueError("query is required")
        if self._intent.company:
            try:
                from fuzzywuzzy import process  # type: ignore
            except ImportError:
                raise ImportError(
                    "fuzzywuzzy is required for fuzzy matching, please install "
                    "it by 'pip install fuzzywuzzy'"
                )

            company_list = ["浙江海翔药业股份有限公司", "江苏安靠智能输电工程科技股份有限公司"]
            hit_company = self._intent.company
            best_match, confidence = process.extractOne(
                self._intent.company, company_list
            )
            if confidence > 60:  # fuzzy match
                hit_company = best_match
            new_query = raw_query.replace(self._intent.company, hit_company)
            request.messages[0].text = new_query
        return request  # type ignore
