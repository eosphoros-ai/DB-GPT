from enum import Enum

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Union, List
import logging

from dbgpt.agent.agents.agent import Agent

logger = logging.getLogger(__name__)


class TeamMode(Enum):
    AUTO_PLAN = "auto_plan"
    AWEL_LAYOUT = "awel_layout"
    SINGLE_AGEN = "singe_agent"


def content_str(content: Union[str, List, None]) -> str:
    """Converts `content` into a string format.

    This function processes content that may be a string, a list of mixed text and image URLs, or None,
    and converts it into a string. Text is directly appended to the result string, while image URLs are
    represented by a placeholder image token. If the content is None, an empty string is returned.

    Args:
        - content (Union[str, List, None]): The content to be processed. Can be a string, a list of dictionaries
                                      representing text and image URLs, or None.

    Returns:
        str: A string representation of the input content. Image URLs are replaced with an image token.

    Note:
    - The function expects each dictionary in the list to have a "type" key that is either "text" or "image_url".
      For "text" type, the "text" key's value is appended to the result. For "image_url", an image token is appended.
    - This function is useful for handling content that may include both text and image references, especially
      in contexts where images need to be represented as placeholders.
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
                "Wrong content format: every element should be dict if the content is a list."
            )
        assert (
            "type" in item
        ), "Wrong content format. Missing 'type' key in content's dict."
        if item["type"] == "text":
            rst += item["text"]
        elif item["type"] == "image_url":
            rst += "<image>"
        else:
            raise ValueError(
                f"Wrong content format: unknown type {item['type']} within the content"
            )
    return rst


class Team:
    def __init__(self):
        self.agents: List[Agent] = []
        self.messages: List[Dict] = []
        self.max_round: Optional[int] = 10
        self.mode_name: TeamMode

    def hire(self, agents: list[Agent]):
        """Hire roles to cooperate"""
        self.agents.extend(agents)

    @property
    def agent_names(self) -> List[str]:
        """Return the names of the agents in the group chat."""
        return [agent.name for agent in self.agents]

    def agent_by_name(self, name: str) -> Agent:
        """Returns the agent with a given name."""
        return self.agents[self.agent_names.index(name)]

    async def a_select_speaker(self, last_speaker: Agent, selector: Agent):
        pass

    def reset(self):
        """Reset the group chat."""
        self.messages.clear()

    def append(self, message: Dict):
        """Append a message to the group chat.
        We cast the content to str here so that it can be managed by text-based
        model.
        """
        message["content"] = content_str(message["content"])
        self.messages.append(message)

    async def a_run_chat(
        self,
        message: Optional[str] = None,
        sender: Optional[Agent] = None,
        reviewer: Agent = None,
    ):
        """
        Install the current organization method to open the conversation
        Args:
            message:
            sender:
            reviewer:

        Returns:

        """
        pass
