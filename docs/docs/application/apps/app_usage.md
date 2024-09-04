# Data App Usage

Starting with version 0.5.0, the DB-GPT project has natively integrated the management and distribution of data-centric applications. The application management repository is also part of the open-source [dbgpts](https://github.com/eosphoros-ai/dbgpts) project. The [dbgpts](https://github.com/eosphoros-ai/dbgpts) project manages and shares resources categorized into the following:

- [apps](https://github.com/eosphoros-ai/dbgpts/tree/main/apps): These are native intelligent data applications developed using the DB-GPT framework.
- [workflow](https://github.com/eosphoros-ai/dbgpts/tree/main/workflow): Workflows constructed using the AWEL (Agentic Workflow Expression Language).
- [agents](https://github.com/eosphoros-ai/dbgpts/tree/main/agents): Intelligent agents that can perform various tasks.
- [operators](https://github.com/eosphoros-ai/dbgpts/tree/main/operators): Basic operational operators (or symbols) that can be used within workflows.

:::info NOTE

Please note that this tutorial primarily focuses on the installation and use of intelligent agent workflows. For the development of applications, you should refer to the `Development Guide`.

Support for these capabilities is provided from version V0.5.0 onwards. For developers and teams looking to build and distribute their applications through DB-GPT, this structured approach provides both a framework and ecosystem for creating, sharing, and managing data applications effectively.
:::

Here we introduce the creation of a data intelligence analysis assistant application. This tutorial utilizes the auto-planning capability of Multi-Agents.

The effect is as follows:

<p align="left">
  <img src={'/img/app/app_analysis.png'} width="720px" />
</p>

In the application panel, click on `Create Application` and fill in the parameters as shown in the image. It is important to note that the work mode selected here is `auto_plan`. This involves the collaboration of two dependent Agents: 1. DataScientist and 2. Reporter. Both of these agents depend on the resource `database`, and for testing, you can use the default database and data provided in the official tutorial.

Special Note: Currently, in auto-plan mode, the building of applications is conducted through multiple Agents. This project has a number of built-in Agents, which currently include:
- [CodeEngineer](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/agents/expand/code_assistant_agent.py)
- [Reporter](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/agents/expand/dashboard_assistant_agent.py)
- [DataScientist](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/agents/expand/data_scientist_agent.py)
- [ToolExpert](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/agents/expand/plugin_assistant_agent.py)
- [RetrieveSummarizer](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/agents/expand/retrieve_summary_assistant_agent.py)
- [Summarizer](https://github.com/eosphoros-ai/DB-GPT/blob/main/dbgpt/agent/agents/expand/summary_assistant_agent.py)

If you wish to expand and implement customized Agents, you can refer to the `Agents Development Guide`.

<p align="left">
  <img src={'/img/app/app_agents.png'} width="720px" />
</p>

<p align="left">
  <img src={'/img/app/app_agent_reporter.jpg'} width="720px" />
</p>

After adding the necessary information, choose to submit to complete the creation of the application. In the application panel, click the dialogue button to enter the dialogue interface.

<p align="left">
  <img src={'/img/app/app_list.png'} width="720px" />
</p>

<p align="left">
  <img src={'/img/app/app_analysis_black.png'} width="720px" />
</p>


# Summary
This tutorial is just a simple introduction to application construction. If you are interested in more complex applications, you can achieve more intricate scenarios by orchestrating AWEL workflows and customizing the expansion of Agents.


