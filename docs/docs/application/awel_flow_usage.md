# AWEL Flow Usage

:::info NOTE

⚠️ Please note that this tutorial mainly introduces the installation and use of agent workflows. For the development of workflows, please refer to the `Development Guide`.
This capability is supported after version V0.5.0.
:::

<p align="left">
  <img src={'/img/app/dbgpts_flow_black.png'} width="720px" />
</p>

As shown in the picture, this is the management and editing interface for DB-GPT workflows. Intelligent agents can be orchestrated into definitive workflows using the Agentic Workflow Expression Language (AWEL). These workflows can be used for subsequent application creation.

<p align="left">
  <img src={'/img/app/awel_flow_node.png'} width="720px" />
</p>

## Workflow Installation

As part of this introductory tutorial, we will cover the installation and use of workflows.

Before you can start using workflows, you need to complete the installation and deployment of DB-GPT. For detailed deployment instructions, you can refer to the quick start guide. Once the project is deployed, you can begin installing and using AWEL workflows. The DB-GPT official provides an application repository that can be used for installation. Here, we will use the command line for operation. Execute `dbgpt --help` in the terminal to check if the command line is installed correctly.

<p align="left">
  <img src={'/img/app/dbgpts_cli.png'} width="720px" />
</p>

As illustrated, the dbgpt command supports various operations, including model-related tasks, knowledge base interactions, Trace logs, and more. Here, we will focus on the operations related to apps.

<p align="left">
  <img src={'/img/app/dbgpts_apps.png'} width="720px" />
</p>

By using the `dbgpt app list-remote` command, we can see that there are three available AWEL workflows in the current repository. Here, we will install the `awel-flow-web-info-search` workflow. To do this, execute the command dbgpt app install `awel-flow-web-info-search`.

Let's also install the other official workflows provided:

```
dbgpt app install awel-flow-web-info-search
dbgpt app install awel-flow-example-chat
dbgpt app install awel-flow-simple-streaming-chat
```
By executing these commands, you will install the respective workflows onto your system.

<p align="left">
  <img src={'/img/app/dbgpts_app_install.png'} width="720px" />
</p>

After successful installation, restart the DB-GPT service (dynamic hot loading is on the way 😊). Refresh the page, and you will be able to see the corresponding workflows on the AWEL workflow page.

## Creating Applications Based on Workflows

Earlier, we introduced the construction and installation of AWEL workflows. Next, let's discuss how to create data applications based on large models.

Here, we will create a search dialogue application based on the `awel-flow-web-info-search` workflow.

The core capability of the search dialogue application is to search for relevant knowledge using a search engine (such as Baidu or Google) and then provide a summarized answer. The effect is as follows:

<p align="left">
  <img src={'/img/app/app_search.png'} width="720px" />
</p>

Creating the aforementioned application is very simple. In the application creation panel, click `Create`, enter the following parameters, and the creation process will be complete. There are a few parameters that require attention:

- Work Mode
- Flows
The work mode we are using here is `awel_layout`. The AWEL workflow selected is `awel-flow-web-info-search`, which is the workflow that was installed previously.

<p align="left">
  <img src={'/img/app/app_awel.png'} width="720px" />
</p>

The above is the basic introduction to using the intelligent agent workflow. We look forward to more of your suggestions on how to play around with it. For instructions on how to develop workflows, you can refer to the development tutorial that follows.

