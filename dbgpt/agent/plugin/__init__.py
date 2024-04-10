"""Plugin module for agent."""

from .commands.command_manage import CommandRegistry  # noqa: F401
from .generator import PluginPromptGenerator  # noqa: F401

__ALL__ = ["PluginPromptGenerator", "CommandRegistry"]
