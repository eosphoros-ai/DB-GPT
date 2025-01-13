"""Base classes for managing a group of agents in a team chat."""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from dbgpt._private.pydantic import BaseModel, ConfigDict, Field

from .agent import Agent, AgentMessage
from .base_agent import ConversableAgent
from .profile import ProfileConfig

logger = logging.getLogger(__name__)


def _content_str(content: Union[str, List, None]) -> str:
    """Convert content into a string format.

    This function processes content that may be a string, a list of mixed text and
    image URLs, or None, and converts it into a string. Text is directly appended to
    the result string, while image URLs are represented by a placeholder image token.
    If the content is None, an empty string is returned.

    Args:
        content (Union[str, List, None]): The content to be processed. Can be a
            string, a list of dictionaries representing text and image URLs, or None.

    Returns:
        str: A string representation of the input content. Image URLs are replaced with
            an image token.

    Note:
    - The function expects each dictionary in the list to have a "type" key that is
        either "text" or "image_url".
        For "text" type, the "text" key's value is appended to the result.
        For "image_url", an image token is appended.
    - This function is useful for handling content that may include both text and image
        references, especially in contexts where images need to be represented as
        placeholders.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise TypeError(f"content must be None, str, or list, but got {type(content)}")

    rst = ""
    for item in content:
        if not isinstance(item, dict):
            raise TypeError(
                "Wrong content format: every element should be dict if the content is "
                "a list."
            )
        assert "type" in item, (
            "Wrong content format. Missing 'type' key in content's dict."
        )
        if item["type"] == "text":
            rst += item["text"]
        elif item["type"] == "image_url":
            rst += "<image>"
        else:
            raise ValueError(
                f"Wrong content format: unknown type {item['type']} within the content"
            )
    return rst


class Team(BaseModel):
    """Team class for managing a group of agents in a team chat."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    agents: List[Agent] = Field(default_factory=list)
    messages: List[Dict] = Field(default_factory=list)
    max_round: int = 100
    is_team: bool = True

    def __init__(self, **kwargs):
        """Create a new Team instance."""
        super().__init__(**kwargs)

    def hire(self, agents: List[Agent]):
        """Hire roles to cooperate."""
        self.agents.extend(agents)

    @property
    def agent_names(self) -> List[str]:
        """Return the names of the agents in the group chat."""
        return [agent.role for agent in self.agents]

    def agent_by_name(self, name: str) -> Agent:
        """Return the agent with a given name."""
        return self.agents[self.agent_names.index(name)]

    async def select_speaker(
        self,
        last_speaker: Agent,
        selector: Agent,
        now_goal_context: Optional[str] = None,
        pre_allocated: Optional[str] = None,
    ) -> Tuple[Agent, Optional[str]]:
        """Select the next speaker in the group chat."""
        raise NotImplementedError

    def reset(self):
        """Reset the group chat."""
        self.messages.clear()

    def append(self, message: Dict):
        """Append a message to the group chat.

        We cast the content to str here so that it can be managed by text-based
        model.
        """
        message["content"] = _content_str(message["content"])
        self.messages.append(message)


class ManagerAgent(ConversableAgent, Team):
    """Manager Agent class."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    profile: ProfileConfig = ProfileConfig(
        name="ManagerAgent",
        profile="TeamManager",
        goal="manage all hired intelligent agents to complete mission objectives",
        constraints=[],
        desc="manage all hired intelligent agents to complete mission objectives",
    )

    is_team: bool = True

    # The management agent does not need to retry the exception. The actual execution
    # of the agent has already been retried.
    max_retry_count: int = 1

    def __init__(self, **kwargs):
        """Create a new ManagerAgent instance."""
        ConversableAgent.__init__(self, **kwargs)
        Team.__init__(self, **kwargs)

    async def thinking(
        self,
        messages: List[AgentMessage],
        sender: Optional[Agent] = None,
        prompt: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Think and reason about the current task goal."""
        # TeamManager, which is based on processes and plans by default, only needs to
        # ensure execution and does not require additional thinking.
        if messages is None or len(messages) <= 0:
            return None, None
        else:
            message = messages[-1]
            self.messages.append(message.to_llm_message())
            return message.content, None

    async def _load_thinking_messages(
        self,
        received_message: AgentMessage,
        sender: Agent,
        rely_messages: Optional[List[AgentMessage]] = None,
        historical_dialogues: Optional[List[AgentMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
        is_retry_chat: bool = False,
    ) -> Tuple[List[AgentMessage], Optional[Dict]]:
        """Load messages for thinking."""
        return [AgentMessage(content=received_message.content)], None
