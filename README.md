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
     <a href="https://github.com/eosphoros-ai/DB-GPT/releases">
      <img alt="Release Notes" src="https://img.shields.io/github/release/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT/issues">
      <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://discord.gg/7uQnPuveTY">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[**简体中文**](README.zh.md) | [**Discord**](https://discord.gg/7uQnPuveTY) | [**Documents**](https://docs.dbgpt.site) | [**Wechat**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**Community**](https://github.com/eosphoros-ai/community)
</div>

## What is DB-GPT?

DB-GPT is an open-source framework designed for the realm of large language models (LLMs) within the database field. Its primary purpose is to provide infrastructure that simplifies and streamlines the development of database-related applications. This is accomplished through the development of various technical capabilities, including:

1. **SMMF(Service-oriented Multi-model Management Framework)**
2. **Text2SQL Fine-tuning**
3. **RAG(Retrieval Augmented Generation) framework and optimization**
4. **Data-Driven Agents framework collaboration**
5. **GBI(Generative Business intelligence)**

DB-GPT simplifies the creation of these applications based on large language models (LLMs) and databases. 

In the era of Data 3.0, enterprises and developers can take the ability to create customized applications with minimal coding, which harnesses the power of large language models (LLMs) and databases.


## Contents
- [Install](#install)
- [Demo](#demo)
- [Introduction](#introduction)
- [Features](#features)
- [Contribution](#contribution)
- [Roadmap](#roadmap)
- [Contact](#contact-information)

[DB-GPT Youtube Video](https://www.youtube.com/watch?v=f5_g0OObZBQ)

## Demo
##### Chat Data
![chatdata](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/1f77079e-d018-4eee-982b-9b6a66bf1063)

##### Chat Excel
![excel](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/3044e83b-a71e-41fe-a1e2-98e479e0ab59)

## Install 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**Usage Tutorial**](http://docs.dbgpt.site/docs/overview)
- [**Install**](http://docs.dbgpt.site/docs/installation)
- [**Quickstart**](http://docs.dbgpt.site/docs/quickstart)
- [**Application**](http://docs.dbgpt.site/docs/operation_manual)
- [**Debugging**](http://docs.dbgpt.site/docs/operation_manual/advanced_tutorial/debugging)


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
    - 🔥🔥🔥  [qwen-72b-chat](https://huggingface.co/Qwen/Qwen-72B-Chat)
    - 🔥🔥🔥  [Yi-34B-Chat](https://huggingface.co/01-ai/Yi-34B-Chat)
  - [More Supported LLMs](http://docs.dbgpt.site/docs/modules/smmf)

- **Privacy and Security**
  
  We ensure the privacy and security of data through the implementation of various technologies, including privatized large models and proxy desensitization.

- Support Datasources
  - [Datasources](http://docs.dbgpt.site/docs/modules/connections)

## Introduction 
The architecture of DB-GPT is shown in the following figure:

<p align="center">
  <img src="./assets/DB-GPT.png" width="800" />
</p>

The core capabilities primarily consist of the following components:
1. Multi-Models: We support multiple Large Language Models (LLMs) such as LLaMA/LLaMA2, CodeLLaMA, ChatGLM, QWen, Vicuna, and proxy models like ChatGPT, Baichuan, Tongyi, Wenxin, and more.
2. Knowledge-Based QA: Our system enables high-quality intelligent Q&A based on local documents such as PDFs, Word documents, Excel files, and other data sources.
3. Embedding: We offer unified data vector storage and indexing. Data is embedded as vectors and stored in vector databases, allowing for content similarity search.
4. Multi-Datasources: This feature connects different modules and data sources, facilitating data flow and interaction.
5. Multi-Agents: Our platform provides Agent and plugin mechanisms, empowering users to customize and enhance the system's behaviour.
6. Privacy & Security: Rest assured that there is no risk of data leakage, and your data is 100% private and secure.
7. Text2SQL: We enhance Text-to-SQL performance through Supervised Fine-Tuning (SFT) applied to Large Language Models (LLMs).

### SubModule
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) Text-to-SQL workflow with high performance by applying Supervised Fine-Tuning (SFT) on Large Language Models (LLMs).
- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT Plugins that can run Auto-GPT plugin directly
- [DB-GPT-Web](https://github.com/eosphoros-ai/DB-GPT-Web)  ChatUI for DB-GPT  

## Image
🌐 [AutoDL Image](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)


### Language Switching
    In the .env configuration file, modify the LANGUAGE parameter to switch to different languages. The default is English (Chinese: zh, English: en, other languages to be added later).

## Contribution

- Please run `black .` before submitting the code.
- To check detailed guidelines for new contributions, please refer [how to contribute](https://github.com/csunny/DB-GPT/blob/main/CONTRIBUTING.md)

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
- [x] [Cluster Deployment](https://docs.dbgpt.site/docs/installation/model_service/cluster)
- [x] [Fastchat Support](https://github.com/lm-sys/FastChat)
- [x] [vLLM Support](https://docs.dbgpt.site/docs/installation/advanced_usage/vLLM_inference)
- [ ] Cloud-native environment and support for Ray environment
- [ ] Service Registry(eg:nacos)
- [ ] Compatibility with OpenAI's interfaces
- [ ] Expansion and optimization of embedding models

### Agents market and Plugins
- [x] multi-agents framework
- [x] custom plugin development 
- [x] plugin market
- [ ] Integration with CoT
- [ ] Enrich plugin sample library
- [ ] Support for AutoGPT protocol
- [ ] Integration of multi-agents and visualization capabilities, defining LLM+Vis new standards

### Cost and Observability
- [x] [debugging](https://docs.dbgpt.site/docs/application_manual/advanced_tutorial/debugging)
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
As of October 10, 2023, through the fine-tuning of an open-source model with 13 billion parameters using this project, we have achieved execution accuracy on the Spider dataset that surpasses even GPT-4!

[More Information about Text2SQL finetune](https://github.com/eosphoros-ai/DB-GPT-Hub)

## Licence


## Contact Information
We are working on building a community, if you have any ideas for building the community, feel free to contact us.
[![](https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat)](https://discord.gg/7uQnPuveTY)

<p align="center">
  <img src="./assets/wechat.jpg" width="300px" />
</p>

[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
