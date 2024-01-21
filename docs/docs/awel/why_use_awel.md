# Why use AWEL?

AWEL (Agentic Workflow Expression Language) is an intelligent agent workflow expression language specifically designed for the development of LLMs applications. In the design of DB-GPT, Agents are considered first-class citizens. RAGs, Datasources (DS), SMMF(Service-oriented Multi-model Management Framework), and Plugins are all resources that agents depend on.

We currently also see that the auto-orchestration capabilities of multi-agents are greatly limited by the model's capabilities, and at the same time, for scenarios that require determinism. For instance, tasks like pipeline work do not need to utilize the auto-orchestration capabilities of large models. Therefore, in DB-GPT, the integration of AWEL with agents can satisfy the implementation of a production-level pipeline and the auto-orchestration of agents systems that address open-ended problems.


Through the orchestration capabilities of AWEL, it is possible to develop large language model applications with a minimal amount of code.

**AWEL  and  agents are all you need**. 