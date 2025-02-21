"""Profiling module.

Autonomous agents typically perform tasks by assuming specific roles, such as coders,
teachers and domain experts.

The profiling module aims to indicate the profiles of the agent roles, which are usually
 written into the prompt to influence the LLM behaviors.

Agent profiles typically encompass basic information such as age, gender, and career,
as well as psychology information, reflecting the personalities of the agent, and social
 information, detailing the relationships between agents.

The choice of analysis information depends heavily on the application scenario.

How to create a profile:
1. Handcrafting method
2. LLM-generation method
3. Dataset alignment method
"""

from dbgpt.util.configure import DynConfig  # noqa: F401

from .base import (  # noqa: F401
    CompositeProfileFactory,
    DatasetProfileFactory,
    DefaultProfile,
    LLMProfileFactory,
    Profile,
    ProfileConfig,
    ProfileFactory,
)
