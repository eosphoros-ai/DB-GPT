import dataclasses
import logging
from typing import Any, List, Optional, Type, cast

from dbgpt._private.config import Config
from dbgpt.agent.resource.knowledge import (
    RetrieverResource,
    RetrieverResourceParameters,
)
from dbgpt.serve.rag.retriever.knowledge_space import KnowledgeSpaceRetriever
from dbgpt.util import ParameterDescription

CFG = Config()

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class KnowledgeSpaceLoadResourceParameters(RetrieverResourceParameters):
    space_name: str = dataclasses.field(
        default=None, metadata={"help": "Knowledge space name"}
    )

    @classmethod
    def _resource_version(cls) -> str:
        """Return the resource version."""
        return "v1"

    @classmethod
    def to_configurations(
        cls,
        parameters: Type["KnowledgeSpaceLoadResourceParameters"],
        version: Optional[str] = None,
    ) -> Any:
        """Convert the parameters to configurations."""
        conf: List[ParameterDescription] = cast(
            List[ParameterDescription], super().to_configurations(parameters)
        )
        version = version or cls._resource_version()
        if version != "v1":
            return conf
        # Compatible with old version
        for param in conf:
            if param.param_name == "space_name":
                return param.valid_values or []
        return []

    @classmethod
    def from_dict(
        cls, data: dict, ignore_extra_fields: bool = True
    ) -> "KnowledgeSpaceLoadResourceParameters":
        """Create a new instance from a dictionary."""
        copied_data = data.copy()
        if "space_name" not in copied_data and "value" in copied_data:
            copied_data["space_name"] = copied_data.pop("value")
        return super().from_dict(copied_data, ignore_extra_fields=ignore_extra_fields)


class KnowledgeSpaceRetrieverResource(RetrieverResource):
    """Knowledge Space retriever resource."""

    def __init__(self, name: str, space_name: str):
        retriever = KnowledgeSpaceRetriever(space_name=space_name)
        super().__init__(name, retriever=retriever)

    @classmethod
    def resource_parameters_class(cls) -> Type[KnowledgeSpaceLoadResourceParameters]:
        from dbgpt.app.knowledge.request.request import KnowledgeSpaceRequest
        from dbgpt.app.knowledge.service import KnowledgeService

        knowledge_space_service = KnowledgeService()
        knowledge_spaces = knowledge_space_service.get_knowledge_space(
            KnowledgeSpaceRequest()
        )
        results = [ks.name for ks in knowledge_spaces]

        @dataclasses.dataclass
        class _DynamicKnowledgeSpaceLoadResourceParameters(
            KnowledgeSpaceLoadResourceParameters
        ):
            space_name: str = dataclasses.field(
                default=None,
                metadata={
                    "help": "Knowledge space name",
                    "valid_values": results,
                },
            )

        return _DynamicKnowledgeSpaceLoadResourceParameters
