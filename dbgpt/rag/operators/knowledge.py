"""Knowledge Operator."""

from typing import Optional

from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    OptionValue,
    Parameter,
    ViewMetadata,
)
from dbgpt.rag.knowledge.base import Knowledge, KnowledgeType
from dbgpt.rag.knowledge.factory import KnowledgeFactory


class KnowledgeOperator(MapOperator[str, Knowledge]):
    """Knowledge Factory Operator."""

    metadata = ViewMetadata(
        label="Knowledge Factory Operator",
        name="knowledge_operator",
        category=OperatorCategory.RAG,
        description="The knowledge operator.",
        inputs=[
            IOField.build_from(
                "knowledge datasource",
                "knowledge datasource",
                str,
                "knowledge datasource",
            )
        ],
        outputs=[
            IOField.build_from(
                "Knowledge",
                "Knowledge",
                Knowledge,
                description="Knowledge",
            )
        ],
        parameters=[
            Parameter.build_from(
                label="datasource",
                name="datasource",
                type=str,
                optional=True,
                default="DOCUMENT",
                description="datasource",
            ),
            Parameter.build_from(
                label="knowledge_type",
                name="knowledge type",
                type=str,
                optional=True,
                options=[
                    OptionValue(
                        label="DOCUMENT",
                        name="DOCUMENT",
                        value=KnowledgeType.DOCUMENT.name,
                    ),
                    OptionValue(label="URL", name="URL", value=KnowledgeType.URL.name),
                    OptionValue(
                        label="TEXT", name="TEXT", value=KnowledgeType.TEXT.name
                    ),
                ],
                default=KnowledgeType.DOCUMENT.name,
                description="knowledge type",
            ),
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(
        self,
        datasource: Optional[str] = None,
        knowledge_type: Optional[str] = KnowledgeType.DOCUMENT.name,
        **kwargs
    ):
        """Init the query rewrite operator.

        Args:
            knowledge_type: (Optional[KnowledgeType]) The knowledge type.
        """
        super().__init__(**kwargs)
        self._datasource = datasource
        self._knowledge_type = KnowledgeType.get_by_value(knowledge_type)

    async def map(self, datasource: str) -> Knowledge:
        """Create knowledge from datasource."""
        if self._datasource:
            datasource = self._datasource
        return await self.blocking_func_to_async(
            KnowledgeFactory.create, datasource, self._knowledge_type
        )
