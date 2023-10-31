# DB-GPT: Revolutionizing Database Interactions with Private LLM Technology
 
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
    <a href="https://opensource.org/licenses/MIT">
      <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg" />
    </a>
     <a href="https://github.com/eosphoros-ai/DB-GPT/releases">
      <img alt="Release Notes" src="https://img.shields.io/github/release/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT/issues">
      <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://discord.gg/nASQyBjvY">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/nASQyBjvY?compact=true&style=flat" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[**简体中文**](README.zh.md) |[**Discord**](https://discord.gg/nASQyBjvY) |[**Documents**](https://db-gpt.readthedocs.io/en/latest/)|[**Wechat**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC)|[**Community**](https://github.com/eosphoros-ai/community)
</div>

## What is DB-GPT?

DB-GPT is an experimental open-source project that uses localized GPT large models to interact with your data and environment. With this solution, you can be assured that there is no risk of data leakage, and your data is 100% private and secure.


## Contents
- [install](#install)
- [demo](#demo)
- [introduction](#introduction)
- [features](#features)
- [contribution](#contribution)
- [roadmap](#roadmap)
- [contact](#contact-information)

[DB-GPT Youtube Video](https://www.youtube.com/watch?v=f5_g0OObZBQ)

## Demo
Run on an RTX 4090 GPU.
##### Chat Excel
![excel](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/0474d220-2a9f-449f-a940-92c8a25af390)
##### Chat Plugin
![auto_plugin_new](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/7d95c347-f4b7-4fb6-8dd2-c1c02babaa56)
##### LLM Management
![llm_manage](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/501d6b3f-c4ce-4197-9a6f-f016f8150a11)
##### FastChat && vLLM
![vllm](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/0c9475d2-45ee-4573-aa5a-814f7fd40213)
##### Trace
![trace_new](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/69bd14b8-14d0-4ca9-9cb7-6cef44a2bc93)
##### Chat Knowledge
![kbqa_new](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/72266a48-edef-4c6d-88c6-fbb1a24a6c3e)

## Install 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**Usage Tutorial**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html)
- [**Install**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html)
  - [**Install Step by Step**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html)
  - [**Docker Install**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/docker/docker.html)
  - [**Docker Compose**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/docker_compose/docker_compose.html)
- [**How to Use**](https://db-gpt.readthedocs.io/en/latest/getting_started/application/chatdb/chatdb.html)
  - [**ChatData**](https://db-gpt.readthedocs.io/en/latest/getting_started/application/chatdb/chatdb.html)
  - [**ChatKnowledge**](https://db-gpt.readthedocs.io/en/latest/getting_started/application/kbqa/kbqa.html)
  - [**ChatExcel**](https://db-gpt.readthedocs.io/en/latest/getting_started/application/chatexcel/chatexcel.html)
  - [**Dashboard**](https://db-gpt.readthedocs.io/en/latest/getting_started/application/dashboard/dashboard.html)
  - [**LLM Management**](https://db-gpt.readthedocs.io/en/latest/getting_started/application/model/model.html)
  - [**Chat Agent**](https://db-gpt.readthedocs.io/en/latest/getting_started/application/chatagent/chatagent.html)
- [**How to Deploy LLM**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/cluster/cluster.html)
  - [**Standalone**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/cluster/vms/standalone.html)
  - [**Cluster**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/cluster/vms/index.html)
  - [**vLLM**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/llm/vllm/vllm.html)
- [**How to Debug**](https://db-gpt.readthedocs.io/en/latest/getting_started/observability.html)
- [**FAQ**](https://db-gpt.readthedocs.io/en/latest/getting_started/faq/deploy/deploy_faq.html)


## Features

Currently, we have released multiple key features, which are listed below to demonstrate our current capabilities:
- Private KBQA & data processing

  The DB-GPT project offers a range of features to enhance knowledge base construction and enable efficient storage and retrieval of both structured and unstructured data. These include built-in support for uploading multiple file formats, the ability to integrate plug-ins for custom data extraction, and unified vector storage and retrieval capabilities for managing large volumes of information.

- Multiple data sources & visualization
  
  The DB-GPT project enables seamless natural language interaction with various data sources, including Excel, databases, and data warehouses. It facilitates effortless querying and retrieval of information from these sources, allowing users to engage in intuitive conversations and obtain insights. Additionally, DB-GPT supports the generation of analysis reports, providing users with valuable summaries and interpretations of the data.

- Multi-Agents&Plugins

  It supports custom plug-ins to perform tasks, natively supports the Auto-GPT plug-in model, and the Agents protocol adopts the Agent Protocol standard.

- Fine-tuning text2SQL

  An automated fine-tuning lightweight framework built around large language models, Text2SQL data sets, LoRA/QLoRA/Pturning, and other fine-tuning methods, making TextSQL fine-tuning as convenient as an assembly line. [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub)

- Multi LLMs Support, Supports multiple large language models, currently supporting

  Massive model support, including dozens of large language models such as open source and API agents. Such as LLaMA/LLaMA2, Baichuan, ChatGLM, Wenxin, Tongyi, Zhipu, etc.
  - [Vicuna](https://huggingface.co/Tribbiani/vicuna-13b)
  - [vicuna-13b-v1.5](https://huggingface.co/lmsys/vicuna-13b-v1.5)
  - [LLama2](https://huggingface.co/meta-llama/Llama-2-7b-chat-hf)
  - [baichuan2-13b](https://huggingface.co/baichuan-inc)
  - [baichuan-7B](https://huggingface.co/baichuan-inc/baichuan-7B)
  - [chatglm-6b](https://huggingface.co/THUDM/chatglm-6b)
  - [chatglm2-6b](https://huggingface.co/THUDM/chatglm2-6b)
  - [falcon-40b](https://huggingface.co/tiiuae/falcon-40b)
  - [internlm-chat-7b](https://huggingface.co/internlm/internlm-chat-7b)
  - [Qwen-7B-Chat/Qwen-14B-Chat](https://huggingface.co/Qwen/)
  - [RWKV-4-Raven](https://huggingface.co/BlinkDL/rwkv-4-raven)
  - [CAMEL-13B-Combined-Data](https://huggingface.co/camel-ai/CAMEL-13B-Combined-Data)
  - [dolly-v2-12b](https://huggingface.co/databricks/dolly-v2-12b)
  - [h2ogpt-gm-oasst1-en-2048-open-llama-7b](https://huggingface.co/h2oai/h2ogpt-gm-oasst1-en-2048-open-llama-7b)
  - [fastchat-t5-3b-v1.0](https://huggingface.co/lmsys/fastchat-t5)
  - [mpt-7b-chat](https://huggingface.co/mosaicml/mpt-7b-chat)
  - [gpt4all-13b-snoozy](https://huggingface.co/nomic-ai/gpt4all-13b-snoozy)
  - [Nous-Hermes-13b](https://huggingface.co/NousResearch/Nous-Hermes-13b)
  - [codet5p-6b](https://huggingface.co/Salesforce/codet5p-6b)
  - [guanaco-33b-merged](https://huggingface.co/timdettmers/guanaco-33b-merged)
  - [WizardLM-13B-V1.0](https://huggingface.co/WizardLM/WizardLM-13B-V1.0)
  - [WizardLM/WizardCoder-15B-V1.0](https://huggingface.co/WizardLM/WizardCoder-15B-V1.0)
  - [Llama2-Chinese-13b-Chat](https://huggingface.co/FlagAlpha/Llama2-Chinese-13b-Chat)
  - [OpenLLaMa OpenInstruct](https://huggingface.co/VMware/open-llama-7b-open-instruct)

  Etc.

  - Support API Proxy LLMs
    - [x] [ChatGPT](https://api.openai.com/)
    - [x] [Tongyi](https://www.aliyun.com/product/dashscope)
    - [x] [Wenxin](https://cloud.baidu.com/product/wenxinworkshop?track=dingbutonglan)
    - [x] [ChatGLM](http://open.bigmodel.cn/)

- Privacy and security
  
  The privacy and security of data are ensured through various technologies, such as privatized large models and proxy desensitization.

- Support Datasources

| DataSource                                                                      | support     | Notes                                       |
| ------------------------------------------------------------------------------  | ----------- | ------------------------------------------- |
| [MySQL](https://www.mysql.com/)                                                 | Yes         |                                             |
| [PostgreSQL](https://www.postgresql.org/)                                      | Yes         |                                             |
| [Spark](https://github.com/apache/spark)                                        | Yes         |                                             |
| [DuckDB](https://github.com/duckdb/duckdb)                                      | Yes         |                                             |
| [Sqlite](https://github.com/sqlite/sqlite)                                      | Yes         |                                             |
| [MSSQL](https://github.com/microsoft/mssql-jdbc)                                | Yes         |                                             |
| [ClickHouse](https://github.com/ClickHouse/ClickHouse)                          | Yes         |                                             |
| [Oracle](https://github.com/oracle)                                             | No          |           TODO                              |
| [Redis](https://github.com/redis/redis)                                         | No          |           TODO                              |
| [MongoDB](https://github.com/mongodb/mongo)                                     | No          |           TODO                              |
| [HBase](https://github.com/apache/hbase)                                        | No          |           TODO                              |
| [Doris](https://github.com/apache/doris)                                        | No          |           TODO                              |
| [DB2](https://github.com/IBM/Db2)                                               | No          |           TODO                              |
| [Couchbase](https://github.com/couchbase)                                       | No          |           TODO                              |
| [Elasticsearch](https://github.com/elastic/elasticsearch)                       | No          |           TODO                              |
| [OceanBase](https://github.com/OceanBase)                                       | No          |           TODO                              |
| [TiDB](https://github.com/pingcap/tidb)                                         | No          |           TODO                              |
| [StarRocks](https://github.com/StarRocks/starrocks)                             | No          |           TODO                              |

## Introduction 
The architecture of the entire DB-GPT is shown.

<p align="center">
  <img src="./assets/DB-GPT.png" width="800" />
</p>

The core capabilities mainly consist of the following parts:
1. Multi-Models: Support multi-LLMs, such as LLaMA/LLaMA2、CodeLLaMA、ChatGLM, QWen、Vicuna and proxy model ChatGPT、Baichuan、tongyi、wenxin etc
2. Knowledge-Based QA: You can perform high-quality intelligent Q&A based on local documents such as PDF, word, excel, and other data.
3. Embedding: Unified data vector storage and indexing, Embed data as vectors and store them in vector databases, providing content similarity search.
4. Multi-Datasources: Used to connect different modules and data sources to achieve data flow and interaction. 
5. Multi-Agents: Provides Agent and plugin mechanisms, allowing users to customize and enhance the system's behavior.
6. Privacy & Secure: You can be assured that there is no risk of data leakage, and your data is 100% private and secure.
7. Text2SQL: We enhance the Text-to-SQL performance by applying Supervised Fine-Tuning (SFT) on large language models

### RAG-IN-Action
<p align="center">
  <img src="./assets/RAG-IN-ACTION.jpg" width="800px" />
</p>

### SubModule
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) Text-to-SQL performance by applying Supervised Fine-Tuning (SFT) on large language models.
- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT Plugins Can run autogpt plugin directly
- [DB-GPT-Web](https://github.com/eosphoros-ai/DB-GPT-Web)  ChatUI for DB-GPT  

## Image
🌐 [AutoDL Image](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)




### Language Switching
    In the .env configuration file, modify the LANGUAGE parameter to switch to different languages. The default is English (Chinese: zh, English: en, other languages to be added later).

## Contribution

- Please run `black .` before submitting the code. Contributing guidelines, [how to contribution](https://github.com/csunny/DB-GPT/blob/main/CONTRIBUTING.md)

## RoadMap

<p align="left">
  <img src="./assets/roadmap.jpg" width="800px" />
</p>

### KBQA RAG optimization
- [x] Multi Documents
  - [x] PDF
  - [x] Excel, CSV
  - [x] Word
  - [x] Text
  - [x] MarkDown
  - [ ] Code
  - [ ] Images 

- [x] RAG
- [ ] Graph Database
  - [ ] Neo4j Graph
  - [ ] Nebula Graph
- [x] Multi-Vector Database
  - [x] Chroma
  - [x] Milvus
  - [x] Weaviate
  - [x] PGVector
  - [ ] Elasticsearch
  - [ ] ClickHouse
  - [ ] Faiss 
  
- [ ] Testing and Evaluation Capability Building
  - [ ] Knowledge QA datasets
  - [ ] Question collection [easy, medium, hard]:
  - [ ] Scoring mechanism
  - [ ] Testing and evaluation using Excel + DB datasets
  
### Multi Datasource Support

- Multi Datasource Support 
  - [x] MySQL
  - [x] PostgreSQL
  - [x] Spark
  - [x] DuckDB
  - [x] Sqlite
  - [x] MSSQL
  - [x] ClickHouse
  - [ ] Oracle
  - [ ] Redis
  - [ ] MongoDB
  - [ ] HBase
  - [ ] Doris
  - [ ] DB2
  - [ ] Couchbase
  - [ ] Elasticsearch
  - [ ] OceanBase
  - [ ] TiDB
  - [ ] StarRocks

### Multi-Models And vLLM
- [x] [Cluster Deployment](https://db-gpt.readthedocs.io/en/latest/getting_started/install/cluster/vms/index.html)
- [x] [Fastchat Support](https://github.com/lm-sys/FastChat)
- [x] [vLLM Support](https://db-gpt.readthedocs.io/en/latest/getting_started/install/llm/vllm/vllm.html)
- [ ] Cloud-native environment and support for Ray environment
- [ ] Service Registry(eg:nacos)
- [ ] Compatibility with OpenAI's interfaces
- [ ] Expansion and optimization of embedding models

### Agents market and Plugins
- [x] multi-agents framework
- [x] custom plugin development 
- [ ] plugin market
- [ ] Integration with CoT
- [ ] Enrich plugin sample library
- [ ] Support for AutoGPT protocol
- [ ] Integration of multi-agents and visualization capabilities, defining LLM+Vis new standards

### Cost and Observability
- [x] [debugging](https://db-gpt.readthedocs.io/en/latest/getting_started/observability.html)
- [ ] Observability
- [ ] cost & budgets

### Text2SQL Finetune
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

As of October 10, 2023, by fine-tuning an open-source model of 13 billion parameters using this project, the execution accuracy on the Spider evaluation dataset has surpassed that of GPT-4!

| name                              | Execution Accuracy | reference                                                                                                                      |
| ----------------------------------| ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| **GPT-4**                         | **0.762**          | [numbersstation-eval-res](https://www.numbersstation.ai/post/nsql-llama-2-7b)                                                  |
| ChatGPT                           | 0.728              | [numbersstation-eval-res](https://www.numbersstation.ai/post/nsql-llama-2-7b)                                                  | 
| **CodeLlama-13b-Instruct-hf_lora**| **0.789**          | sft train by our this project,only used spider train dataset ,the same eval  way in this project  with lora SFT                |
| CodeLlama-13b-Instruct-hf_qlora   | 0.774              | sft train by our this project,only used spider train dataset ,the same eval  way in this project  with qlora and nf4,bit4 SFT  |
| wizardcoder                       | 0.610              | [text-to-sql-wizardcoder](https://github.com/cuplv/text-to-sql-wizardcoder/tree/main)                                          |  
| CodeLlama-13b-Instruct-hf         | 0.556              | eval in this project default param                                                                                             |
| llama2_13b_hf_lora_best           | 0.744              | sft train by our this project,only used spider train dataset ,the same eval  way in this project                               |

[More Information about Text2SQL finetune](https://github.com/eosphoros-ai/DB-GPT-Hub)

## Licence

The MIT License (MIT)

## Contact Information
We are working on building a community, if you have any ideas for building the community, feel free to contact us.
[![](https://dcbadge.vercel.app/api/server/nASQyBjvY?compact=true&style=flat)](https://discord.gg/nASQyBjvY)

<p align="center">
  <img src="./assets/wechat.jpg" width="300px" />
</p>

[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
