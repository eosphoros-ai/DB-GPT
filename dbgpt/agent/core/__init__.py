"""Core Module for the Agent.

There are four modules in DB-GPT agent core according the paper
`A survey on large language model based autonomous agents
<https://link.springer.com/article/10.1007/s11704-024-40231-1>`
by `Lei Wang, Chen Ma, Xueyang Feng, et al.`:

1. Profiling Module: The profiling module aims to indicate the profiles of the agent
roles.

2. Memory Module: It stores information perceived from the environment and leverages
the recorded memories to facilitate future actions.

3. Planning Module: When faced with a complex task, humans tend to deconstruct it into
simpler subtasks and solve them individually. The planning module aims to empower the
agents with such human capability, which is expected to make the agent behave more
reasonably, powerfully, and reliably

4. Action Module: The action module is responsible for translating the agent’s
decisions into specific outcomes. This module is located at the most downstream
position and directly interacts with the environment.
"""
