from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

if TYPE_CHECKING:
    pass


class PromptType(str, Enum):
    """Prompt type."""

    FSCHAT: str = "fschat"
    DBGPT: str = "dbgpt"


class ConversationAdapter(ABC):
    """The conversation adapter."""

    @property
    def prompt_type(self) -> PromptType:
        return PromptType.FSCHAT

    @property
    @abstractmethod
    def roles(self) -> Tuple[str]:
        """Get the roles of the conversation.

        Returns:
            Tuple[str]: The roles of the conversation.
        """

    @property
    def sep(self) -> Optional[str]:
        """Get the separator between messages."""
        return "\n"

    @property
    def stop_str(self) -> Optional[Union[str, List[str]]]:
        """Get the stop criteria."""
        return None

    @property
    def stop_token_ids(self) -> Optional[List[int]]:
        """Stops generation if meeting any token in this list"""
        return None

    @abstractmethod
    def get_prompt(self) -> str:
        """Get the prompt string.

        Returns:
            str: The prompt string.
        """

    @abstractmethod
    def set_system_message(self, system_message: str) -> None:
        """Set the system message."""

    @abstractmethod
    def append_message(self, role: str, message: str) -> None:
        """Append a new message.
        Args:
            role (str): The role of the message.
            message (str): The message content.
        """

    @abstractmethod
    def update_last_message(self, message: str) -> None:
        """Update the last output.

        The last message is typically set to be None when constructing the prompt,
        so we need to update it in-place after getting the response from a model.

        Args:
            message (str): The message content.
        """

    @abstractmethod
    def copy(self) -> "ConversationAdapter":
        """Copy the conversation."""


class ConversationAdapterFactory(ABC):
    """The conversation adapter factory."""

    def get_by_name(
        self,
        template_name: str,
        prompt_template_type: Optional[PromptType] = PromptType.FSCHAT,
    ) -> ConversationAdapter:
        """Get a conversation adapter by name.

        Args:
            template_name (str): The name of the template.
            prompt_template_type (Optional[PromptType]): The type of the prompt
             template, default to be FSCHAT.

        Returns:
            ConversationAdapter: The conversation adapter.
        """
        raise NotImplementedError()

    def get_by_model(self, model_name: str, model_path: str) -> ConversationAdapter:
        """Get a conversation adapter by model.

        Args:
            model_name (str): The name of the model.
            model_path (str): The path of the model.

        Returns:
            ConversationAdapter: The conversation adapter.
        """
        raise NotImplementedError()


def get_conv_template(name: str) -> ConversationAdapter:
    """Get a conversation template.

    Args:
        name (str): The name of the template.

    Just return the fastchat conversation template for now.
    # TODO: More templates should be supported.
    Returns:
        Conversation: The conversation template.
    """
    from fastchat.conversation import get_conv_template

    from dbgpt.model.adapter.fschat_adapter import FschatConversationAdapter

    conv_template = get_conv_template(name)
    return FschatConversationAdapter(conv_template)
