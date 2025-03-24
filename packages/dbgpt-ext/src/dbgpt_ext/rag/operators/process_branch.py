"""Knowledge Process Branch Operator."""

from typing import Dict, List, Optional

from dbgpt.core import Chunk
from dbgpt.core.awel import (
    BranchFunc,
    BranchOperator,
    BranchTaskType,
    JoinOperator,
    logger,
)
from dbgpt.core.awel.flow import IOField, OperatorCategory, OperatorType, ViewMetadata
from dbgpt.rag.knowledge.base import Knowledge
from dbgpt.util.i18n_utils import _


class KnowledgeProcessBranchOperator(BranchOperator[Knowledge, Knowledge]):
    """Knowledge Process branch operator.

    This operator will branch the workflow based on
    the stream flag of the request.
    """

    metadata = ViewMetadata(
        label=_("Knowledge Process Branch Operator"),
        name="knowledge_process_operator",
        category=OperatorCategory.RAG,
        operator_type=OperatorType.BRANCH,
        description=_("Branch the workflow based on the stream flag of the request."),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Document Chunks"),
                "input_value",
                List[Chunk],
                description=_("The input value of the operator."),
                is_list=True,
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Chunks"),
                "chunks",
                List[Chunk],
                description=_("Chunks for Vector Storage Connector."),
                is_list=True,
            ),
            IOField.build_from(
                _("Chunks"),
                "chunks",
                List[Chunk],
                description=_("Chunks for Knowledge Graph Connector."),
                is_list=True,
            ),
            IOField.build_from(
                _("Chunks"),
                "chunks",
                List[Chunk],
                description=_("Chunks for Full Text Connector."),
                is_list=True,
            ),
        ],
    )

    def __init__(
        self,
        graph_task_name: Optional[str] = None,
        embedding_task_name: Optional[str] = None,
        **kwargs,
    ):
        """Create the intent detection branch operator."""
        super().__init__(**kwargs)
        self._graph_task_name = graph_task_name
        self._embedding_task_name = embedding_task_name
        self._full_text_task_name = embedding_task_name

    async def branches(
        self,
    ) -> Dict[BranchFunc[Knowledge], BranchTaskType]:
        """Branch the intent detection result to different tasks."""
        download_cls_list = set(task.__class__ for task in self.downstream)  # noqa
        branch_func_map = {}

        async def check_graph_process(r: Knowledge) -> bool:
            # If check graph is true, we will run extract knowledge graph triplets.
            from dbgpt_ext.rag.operators import KnowledgeGraphOperator

            if KnowledgeGraphOperator in download_cls_list:
                return True
            return False

        async def check_embedding_process(r: Knowledge) -> bool:
            # If check embedding is true, we will run extract document embedding.
            from dbgpt_ext.rag.operators import VectorStorageOperator

            if VectorStorageOperator in download_cls_list:
                return True
            return False

        async def check_full_text_process(r: Knowledge) -> bool:
            # If check full text is true, we will run extract document keywords.
            from dbgpt_ext.rag.operators.full_text import FullTextStorageOperator

            if FullTextStorageOperator in download_cls_list:
                return True
            return False

        branch_func_map[check_graph_process] = self._graph_task_name
        branch_func_map[check_embedding_process] = self._embedding_task_name
        branch_func_map[check_full_text_process] = self._full_text_task_name
        return branch_func_map  # type: ignore


class KnowledgeProcessJoinOperator(JoinOperator[List[str]]):
    """Knowledge Process Join Operator."""

    metadata = ViewMetadata(
        label=_("Knowledge Process Join Operator"),
        name="knowledge_process_join_operator",
        category=OperatorCategory.RAG,
        operator_type=OperatorType.JOIN,
        description=_(
            "Join Branch the workflow based on the Knowledge Process Results."
        ),
        parameters=[],
        inputs=[
            IOField.build_from(
                _("Vector Storage Results"),
                "input_value",
                List[Chunk],
                description=_("vector storage results."),
                is_list=True,
            ),
            IOField.build_from(
                _("Knowledge Graph Storage Results"),
                "input_value",
                List[Chunk],
                description=_("knowledge graph storage results."),
                is_list=True,
            ),
        ],
        outputs=[
            IOField.build_from(
                _("Chunks"),
                "chunks",
                List[Chunk],
                description=_("Knowledge Process Results."),
                is_list=True,
            ),
        ],
    )

    def __init__(
        self,
        **kwargs,
    ):
        """Knowledge Process Join Operator."""
        super().__init__(combine_function=self._join, **kwargs)

    async def _join(
        self,
        vector_chunks: Optional[List[Chunk]] = None,
        graph_chunks: Optional[List[Chunk]] = None,
        full_text_chunks: Optional[List[Chunk]] = None,
    ) -> List[str]:
        """Join results.

        Args:
            vector_chunks: The list of vector chunks.
            graph_chunks: The list of graph chunks.
            full_text_chunks: The list of full text chunks.
        """
        results = []
        if vector_chunks:
            result_msg = (
                f"async persist vector store success {len(vector_chunks)} chunks."
            )
            logger.info(result_msg)
            results.append(result_msg)
        if graph_chunks:
            result_msg = (
                f"async persist graph store success {len(graph_chunks)} chunks."
            )
            logger.info(result_msg)
            results.append(result_msg)
        if full_text_chunks:
            result_msg = (
                f"async persist full text store success {len(full_text_chunks)} chunks."
            )
            logger.info(result_msg)
            results.append(result_msg)
        return results
