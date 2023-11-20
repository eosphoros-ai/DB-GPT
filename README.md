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
    <a href="https://discord.gg/nASQyBjvY">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/nASQyBjvY?compact=true&style=flat" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[**简体中文**](README.zh.md) | [**Discord**](https://discord.gg/nASQyBjvY) | [**Documents**](https://db-gpt.readthedocs.io/en/latest/) | [**Wechat**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**Community**](https://github.com/eosphoros-ai/community)
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

## Install 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**Usage Tutorial**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html)
- [**Install**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy.html)
  - [**Install Step by Step**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy.html)
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

  - Support API Proxy LLMs
    - [x] [ChatGPT](https://api.openai.com/)
    - [x] [Tongyi](https://www.aliyun.com/product/dashscope)
    - [x] [Wenxin](https://cloud.baidu.com/product/wenxinworkshop?track=dingbutonglan)
    - [x] [ChatGLM](http://open.bigmodel.cn/)

- **Privacy and Security**
  
  We ensure the privacy and security of data through the implementation of various technologies, including privatized large models and proxy desensitization.

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
As of October 10, 2023, through the fine-tuning of an open-source model with 13 billion parameters using this project, we have achieved execution accuracy on the Spider dataset that surpasses even GPT-4!

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
