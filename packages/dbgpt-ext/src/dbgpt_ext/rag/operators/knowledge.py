"""Knowledge Operator."""

from typing import List, Optional

from dbgpt.core import Chunk
from dbgpt.core.awel import MapOperator
from dbgpt.core.awel.flow import (
    IOField,
    OperatorCategory,
    OptionValue,
    Parameter,
    ViewMetadata,
)
from dbgpt.rag.knowledge.base import Knowledge, KnowledgeType
from dbgpt.util.i18n_utils import _
from dbgpt_ext.rag.knowledge.factory import KnowledgeFactory


class KnowledgeOperator(MapOperator[dict, Knowledge]):
    """Knowledge Factory Operator."""

    metadata = ViewMetadata(
        label=_("Knowledge Loader Operator"),
        name="knowledge_operator",
        category=OperatorCategory.RAG,
        description=_(
            _("The knowledge operator, which can create knowledge from datasource.")
        ),
        inputs=[
            IOField.build_from(
                _("knowledge datasource"),
                "knowledge datasource",
                dict,
                _("knowledge datasource, which can be a document, url, or text."),
            )
        ],
        outputs=[
            IOField.build_from(
                _("Knowledge"),
                "Knowledge",
                Knowledge,
                description=_("Knowledge object."),
            )
        ],
        parameters=[
            Parameter.build_from(
                label=_("Default datasource"),
                name="datasource",
                type=str,
                optional=True,
                default=None,
                description=_("Default datasource."),
            ),
            Parameter.build_from(
                label=_("Knowledge type"),
                name="knowledge_type",
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
                description=_("Knowledge type."),
            ),
        ],
        documentation_url="https://github.com/openai/openai-python",
    )

    def __init__(
        self,
        datasource: Optional[str] = None,
        knowledge_type: Optional[str] = KnowledgeType.DOCUMENT.name,
        **kwargs,
    ):
        """Init the query rewrite operator.

        Args:
            knowledge_type: (Optional[KnowledgeType]) The knowledge type.
        """
        super().__init__(**kwargs)
        self._datasource = datasource
        self._knowledge_type = KnowledgeType.get_by_value(knowledge_type)

    async def map(self, datasource: dict) -> Knowledge:
        """Create knowledge from datasource."""
        source = datasource.get("source")
        if self._datasource:
            source = self._datasource
        return await self.blocking_func_to_async(
            KnowledgeFactory.create, source, self._knowledge_type
        )


class ChunksToStringOperator(MapOperator[List[Chunk], str]):
    """The Chunks To String Operator."""

    metadata = ViewMetadata(
        label=_("Chunks To String Operator"),
        name="chunks_to_string_operator",
        description=_("Convert chunks to string."),
        category=OperatorCategory.RAG,
        parameters=[
            Parameter.build_from(
                _("Separator"),
                "separator",
                str,
                description=_("The separator between chunks."),
                optional=True,
                default="\n",
            )
        ],
        inputs=[
            IOField.build_from(
                _("Chunks"),
                "chunks",
                List[Chunk],
                description=_("The input chunks."),
                is_list=True,
            )
        ],
        outputs=[
            IOField.build_from(
                _("String"),
                "string",
                str,
                description=_("The output string."),
            )
        ],
    )

    def __init__(self, separator: str = "\n", **kwargs):
        """Create a new ChunksToStringOperator."""
        self._separator = separator
        super().__init__(**kwargs)

    async def map(self, chunks: List[Chunk]) -> str:
        """Map the chunks to string."""
        return self._separator.join([chunk.content for chunk in chunks])
