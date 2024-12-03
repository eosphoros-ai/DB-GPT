# DB-GPT: AI Native Data App Development framework with AWEL(Agentic Workflow Expression Language) and Agents

<p align="left">
  <img src="./assets/LOGO.png" width="100%" />
</p>

<div align="center">
  <p>
    <a href="https://github.com/eosphoros-ai/DB-GPT">
        <img alt="stars" src="https://img.shields.io/github/stars/eosphoros-ai/db-gpt?style=social" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT">
        <img alt="forks" src="https://img.shields.io/github/forks/eosphoros-ai/db-gpt?style=social" />
    </a>
    <a href="https://opensource.org/licenses/MIT">
      <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg" />
    </a>
     <a href="https://github.com/eosphoros-ai/DB-GPT/releases">
      <img alt="Release Notes" src="https://img.shields.io/github/release/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT/issues">
      <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://discord.gg/7uQnPuveTY">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat" />
    </a>
    <a href="https://join.slack.com/t/slack-inu2564/shared_invite/zt-29rcnyw2b-N~ubOD9kFc7b7MDOAM1otA">
      <img alt="Slack" src="https://badgen.net/badge/Slack/Join%20DB-GPT/0abd59?icon=slack" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[**简体中文**](README.zh.md) | [**日本語**](README.ja.md) | [**Discord**](https://discord.gg/7uQnPuveTY) | [**Documents**](https://docs.dbgpt.site) | [**微信**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**Community**](https://github.com/eosphoros-ai/community) | [**Paper**](https://arxiv.org/pdf/2312.17449.pdf)

</div>

## What is DB-GPT?

🤖 **DB-GPT is an open source AI native data app development framework with AWEL(Agentic Workflow Expression Language) and agents**. 

The purpose is to build infrastructure in the field of large models, through the development of multiple technical capabilities such as multi-model management (SMMF), Text2SQL effect optimization, RAG framework and optimization, Multi-Agents framework collaboration, AWEL (agent workflow orchestration), etc. Which makes large model applications with data simpler and more convenient.


🚀 **In the Data 3.0 era, based on models and databases, enterprises and developers can build their own bespoke applications with less code.**

### AI-Native Data App 
---
- 🔥🔥🔥 [Released V0.6.0 | A set of significant upgrades](https://docs.dbgpt.cn/docs/changelog/Released_V0.6.0)
  - [The AWEL upgrade to 2.0]()
  - [GraphRAG]()
  - [AI Native Data App construction and management]()
  - [The GPT-Vis upgrade, supporting a variety of visualization charts]()
  - [Support Text2NLU and Text2GQL fine-tuning]()
  - [Support Intent recognition, slot filling, and Prompt management]()

---

![app_chat_v0 6](https://github.com/user-attachments/assets/a2f0a875-df8c-4f0d-89a3-eed321c02113)

![app_manage_chat_data_v0 6](https://github.com/user-attachments/assets/c8cc85bb-e3c2-4fab-8fb9-7b4b469d0611)

![chat_dashboard_display_v0 6](https://github.com/user-attachments/assets/b15d6ebe-54c4-4527-a16d-02fbbaf20dc9)

![agent_prompt_awel_v0 6](https://github.com/user-attachments/assets/40761507-a1e1-49d4-b49a-3dd9a5ea41cc)

## Contents
- [Introduction](#introduction)
- [Install](#install)
- [Features](#features)
- [Contribution](#contribution)
- [Contact](#contact-information)

## Introduction 
The architecture of DB-GPT is shown in the following figure:

<p align="center">
  <img src="./assets/dbgpt.png" width="800" />
</p>

The core capabilities include the following parts:

- **RAG (Retrieval Augmented Generation)**: RAG is currently the most practically implemented and urgently needed domain. DB-GPT has already implemented a framework based on RAG, allowing users to build knowledge-based applications using the RAG capabilities of DB-GPT.

- **GBI (Generative Business Intelligence)**: Generative BI is one of the core capabilities of the DB-GPT project, providing the foundational data intelligence technology to build enterprise report analysis and business insights.

- **Fine-tuning Framework**: Model fine-tuning is an indispensable capability for any enterprise to implement in vertical and niche domains. DB-GPT provides a complete fine-tuning framework that integrates seamlessly with the DB-GPT project. In recent fine-tuning efforts, an accuracy rate based on the Spider dataset has been achieved at 82.5%.

- **Data-Driven Multi-Agents Framework**: DB-GPT offers a data-driven self-evolving multi-agents framework, aiming to continuously make decisions and execute based on data.

- **Data Factory**: The Data Factory is mainly about cleaning and processing trustworthy knowledge and data in the era of large models.

- **Data Sources**: Integrating various data sources to seamlessly connect production business data to the core capabilities of DB-GPT.

### SubModule
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) Text-to-SQL workflow with high performance by applying Supervised Fine-Tuning (SFT) on Large Language Models (LLMs).

- [dbgpts](https://github.com/eosphoros-ai/dbgpts)  dbgpts is the official repository which contains some data apps、AWEL operators、AWEL workflow templates and agents which build upon DB-GPT.

#### Text2SQL Finetune
- support llms
  - [x] LLaMA
  - [x] LLaMA-2
  - [x] BLOOM
  - [x] BLOOMZ
  - [x] Falcon
  - [x] Baichuan
  - [x] Baichuan2
  - [x] InternLM
  - [x] Qwen
  - [x] XVERSE
  - [x] ChatGLM2

-  SFT Accuracy
As of October 10, 2023, through the fine-tuning of an open-source model with 13 billion parameters using this project, we have achieved execution accuracy on the Spider dataset that surpasses even GPT-4!

[More Information about Text2SQL finetune](https://github.com/eosphoros-ai/DB-GPT-Hub)

- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT Plugins that can run Auto-GPT plugin directly
- [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) Visualization protocol

## Install 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**Usage Tutorial**](http://docs.dbgpt.cn/docs/overview)
- [**Install**](http://docs.dbgpt.cn/docs/installation)
  - [Docker](http://docs.dbgpt.cn/docs/installation/docker)
  - [Source Code](http://docs.dbgpt.cn/docs/installation/sourcecode)
- [**Quickstart**](http://docs.dbgpt.cn/docs/quickstart)
- [**Application**](http://docs.dbgpt.cn/docs/operation_manual)
  - [Development Guide](http://docs.dbgpt.cn/docs/cookbook/app/data_analysis_app_develop) 
  - [App Usage](http://docs.dbgpt.cn/docs/application/app_usage)
  - [AWEL Flow Usage](http://docs.dbgpt.cn/docs/application/awel_flow_usage)
- [**Debugging**](http://docs.dbgpt.cn/docs/operation_manual/advanced_tutorial/debugging)
- [**Advanced Usage**](http://docs.dbgpt.cn/docs/application/advanced_tutorial/cli)
  - [SMMF](http://docs.dbgpt.cn/docs/application/advanced_tutorial/smmf)
  - [Finetune](http://docs.dbgpt.cn/docs/application/fine_tuning_manual/dbgpt_hub)
  - [AWEL](http://docs.dbgpt.cn/docs/awel/tutorial)


## Features

At present, we have introduced several key features to showcase our current capabilities:
- **Private Domain Q&A & Data Processing**

  The DB-GPT project offers a range of functionalities designed to improve knowledge base construction and enable efficient storage and retrieval of both structured and unstructured data. These functionalities include built-in support for uploading multiple file formats, the ability to integrate custom data extraction plug-ins, and unified vector storage and retrieval capabilities for effectively managing large volumes of information.

- **Multi-Data Source & GBI(Generative Business intelligence)**

  The DB-GPT project facilitates seamless natural language interaction with diverse data sources, including Excel, databases, and data warehouses. It simplifies the process of querying and retrieving information from these sources, empowering users to engage in intuitive conversations and gain insights. Moreover, DB-GPT supports the generation of analytical reports, providing users with valuable data summaries and interpretations.

- **Multi-Agents&Plugins**

  It offers support for custom plug-ins to perform various tasks and natively integrates the Auto-GPT plug-in model. The Agents protocol adheres to the Agent Protocol standard.

- **Automated Fine-tuning text2SQL**

  We've also developed an automated fine-tuning lightweight framework centred on large language models (LLMs), Text2SQL datasets, LoRA/QLoRA/Pturning, and other fine-tuning methods. This framework simplifies Text-to-SQL fine-tuning, making it as straightforward as an assembly line process. [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub)

- **SMMF(Service-oriented Multi-model Management Framework)**

  We offer extensive model support, including dozens of large language models (LLMs) from both open-source and API agents, such as LLaMA/LLaMA2, Baichuan, ChatGLM, Wenxin, Tongyi, Zhipu, and many more. 

  - News
    - 🔥🔥🔥  [Qwen2.5-72B-Instruct](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct)
    - 🔥🔥🔥  [Meta-Llama-3.1-405B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-405B-Instruct)
    - 🔥🔥🔥  [Meta-Llama-3.1-70B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-70B-Instruct)
    - 🔥🔥🔥  [Meta-Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)
    - 🔥🔥🔥  [gemma-2-27b-it](https://huggingface.co/google/gemma-2-27b-it)
    - 🔥🔥🔥  [gemma-2-9b-it](https://huggingface.co/google/gemma-2-9b-it)
    - 🔥🔥🔥  [DeepSeek-Coder-V2-Instruct](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct)
    - 🔥🔥🔥  [DeepSeek-Coder-V2-Lite-Instruct](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct)
    - 🔥🔥🔥  [Qwen2-57B-A14B-Instruct](https://huggingface.co/Qwen/Qwen2-57B-A14B-Instruct)
    - 🔥🔥🔥  [Qwen2-72B-Instruct](https://huggingface.co/Qwen/Qwen2-72B-Instruct)
    - 🔥🔥🔥  [Qwen2-7B-Instruct](https://huggingface.co/Qwen/Qwen2-7B-Instruct)
    - 🔥🔥🔥  [Qwen2-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2-1.5B-Instruct)
    - 🔥🔥🔥  [Qwen2-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2-0.5B-Instruct)
    - 🔥🔥🔥  [glm-4-9b-chat](https://huggingface.co/THUDM/glm-4-9b-chat)
    - 🔥🔥🔥  [Phi-3](https://huggingface.co/collections/microsoft/phi-3-6626e15e9585a200d2d761e3)
    - 🔥🔥🔥  [Yi-1.5-34B-Chat](https://huggingface.co/01-ai/Yi-1.5-34B-Chat)
    - 🔥🔥🔥  [Yi-1.5-9B-Chat](https://huggingface.co/01-ai/Yi-1.5-9B-Chat)
    - 🔥🔥🔥  [Yi-1.5-6B-Chat](https://huggingface.co/01-ai/Yi-1.5-6B-Chat)
    - 🔥🔥🔥  [Qwen1.5-110B-Chat](https://huggingface.co/Qwen/Qwen1.5-110B-Chat)
    - 🔥🔥🔥  [Qwen1.5-MoE-A2.7B-Chat](https://huggingface.co/Qwen/Qwen1.5-MoE-A2.7B-Chat)
    - 🔥🔥🔥  [Meta-Llama-3-70B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct)
    - 🔥🔥🔥  [Meta-Llama-3-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct)
    - 🔥🔥🔥  [CodeQwen1.5-7B-Chat](https://huggingface.co/Qwen/CodeQwen1.5-7B-Chat)
    - 🔥🔥🔥  [Qwen1.5-32B-Chat](https://huggingface.co/Qwen/Qwen1.5-32B-Chat)
    - 🔥🔥🔥  [Starling-LM-7B-beta](https://huggingface.co/Nexusflow/Starling-LM-7B-beta)
    - 🔥🔥🔥  [gemma-7b-it](https://huggingface.co/google/gemma-7b-it)
    - 🔥🔥🔥  [gemma-2b-it](https://huggingface.co/google/gemma-2b-it)
    - 🔥🔥🔥  [SOLAR-10.7B](https://huggingface.co/upstage/SOLAR-10.7B-Instruct-v1.0)
    - 🔥🔥🔥  [Mixtral-8x7B](https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1)
    - 🔥🔥🔥  [Qwen-72B-Chat](https://huggingface.co/Qwen/Qwen-72B-Chat)
    - 🔥🔥🔥  [Yi-34B-Chat](https://huggingface.co/01-ai/Yi-34B-Chat)
  - [More Supported LLMs](http://docs.dbgpt.site/docs/modules/smmf)

- **Privacy and Security**
  
  We ensure the privacy and security of data through the implementation of various technologies, including privatized large models and proxy desensitization.

- Support Datasources
  - [Datasources](http://docs.dbgpt.cn/docs/modules/connections)

## Image
🌐 [AutoDL Image](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)


### Language Switching
    In the .env configuration file, modify the LANGUAGE parameter to switch to different languages. The default is English (Chinese: zh, English: en, other languages to be added later).

## Contribution

- To check detailed guidelines for new contributions, please refer [how to contribute](https://github.com/eosphoros-ai/DB-GPT/blob/main/CONTRIBUTING.md)

### Contributors Wall
<a href="https://github.com/eosphoros-ai/DB-GPT/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=eosphoros-ai/DB-GPT&max=200" />
</a>


## Licence
The MIT License (MIT)

## Citation
If you find `DB-GPT` useful for your research or development, please cite the following <a href="https://arxiv.org/abs/2312.17449" target="_blank">paper</a>:

```bibtex
@article{xue2023dbgpt,
      title={DB-GPT: Empowering Database Interactions with Private Large Language Models}, 
      author={Siqiao Xue and Caigao Jiang and Wenhui Shi and Fangyin Cheng and Keting Chen and Hongjun Yang and Zhiping Zhang and Jianshan He and Hongyang Zhang and Ganglin Wei and Wang Zhao and Fan Zhou and Danrui Qi and Hong Yi and Shaodong Liu and Faqiang Chen},
      year={2023},
      journal={arXiv preprint arXiv:2312.17449},
      url={https://arxiv.org/abs/2312.17449}
}
```

## Contact Information
We are working on building a community, if you have any ideas for building the community, feel free to contact us.
[![](https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat)](https://discord.gg/7uQnPuveTY)

[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
