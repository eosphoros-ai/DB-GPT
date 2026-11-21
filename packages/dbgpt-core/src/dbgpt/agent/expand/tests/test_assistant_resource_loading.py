"""Assistant agents must use every bound knowledge resource (issue #2579).

``SimpleAssistantAgent`` ("AI Assistant") and ``SummaryAssistantAgent`` build
their resource prompt from the pack's sub-resources. They used to index the
retrieved chunks by resource name, so when two knowledge bases had the same name
(the app editor's default), only the last one reached the prompt, and the
references of the last one replaced the others.
"""

import asyncio
from typing import Any, Dict, List, Optional, Tuple

import pytest

from dbgpt.core import Chunk

from ...resource.base import Resource, ResourceType
from ...resource.pack import ResourcePack
from ..simple_assistant_agent import SimpleAssistantAgent
from ..summary_assistant_agent import SummaryAssistantAgent

_DEFAULT_NAME = "My Agent Resource"


class _KnowledgeSpace(Resource):
    """A knowledge resource returning one chunk with the real references shape."""

    def __init__(self, name: str, space: str, retriever: str):
        """Create a resource for one knowledge space."""
        self._name = name
        self._space = space
        self._retriever = retriever

    @classmethod
    def type(cls) -> ResourceType:
        """Return the knowledge resource type."""
        return ResourceType.Knowledge

    @property
    def name(self) -> str:
        """Return the resource name."""
        return self._name

    async def get_prompt(
        self,
        *,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs: Any,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Not used by the assistant agents."""
        raise NotImplementedError

    async def get_resources(
        self,
        lang: str = "en",
        prompt_type: str = "default",
        question: Optional[str] = None,
        resource_name: Optional[str] = None,
    ) -> Tuple[Optional[List[Chunk]], str, Optional[Dict]]:
        """Return one chunk from this space and its references."""
        chunk = Chunk(content=f"from {self._space}", retriever=self._retriever)
        references = {"knowledge": [{"name": f"{self._space}.md", "chunks": []}]}
        return [chunk], "Resources-{name}:\n {content}", references


@pytest.mark.parametrize("agent_cls", [SimpleAssistantAgent, SummaryAssistantAgent])
@pytest.mark.parametrize("retriever", ["embedding_retriever", "qa_retriever"])
def test_same_named_knowledge_resources_all_reach_the_prompt(agent_cls, retriever):
    """Each same-named knowledge base reaches the prompt and the references."""
    agent = agent_cls()
    agent.resource = ResourcePack(
        [
            _KnowledgeSpace(_DEFAULT_NAME, "time", retriever),
            _KnowledgeSpace(_DEFAULT_NAME, "location", retriever),
        ]
    )

    prompt, references = asyncio.run(agent.load_resource("where and when?"))

    assert prompt == (
        f"Resources-{_DEFAULT_NAME}:\n --0--:from time\n"
        f"Resources-{_DEFAULT_NAME}:\n --0--:from location"
    )
    assert [r["name"] for r in references["knowledge"]] == ["time.md", "location.md"]
