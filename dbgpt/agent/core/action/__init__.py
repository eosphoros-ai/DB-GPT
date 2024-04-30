"""Action Module.

The action module is responsible for translating the agent’s decisions into specific
outcomes. This module is located at the most downstream position and directly interacts
with the environment. It is influenced by the profile, memory, and planning modules.


The Goal Of The Action Module:
--------
1. Task Completion: Complete specific tasks, write a function in software development,
and make an iron pick in the game.

2. Communication: Communicate with other agents.

3. Environment exploration: Explore unfamiliar environments to expand its perception
and strike a balance between exploring and exploiting.
"""

from .base import Action, ActionOutput  # noqa: F401
from .blank_action import BlankAction  # noqa: F401
