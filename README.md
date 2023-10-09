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
    <a href="https://discord.gg/vqBrcV7Nd">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/vqBrcV7Nd?compact=true&style=flat" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[**简体中文**](README.zh.md) |[**Discord**](https://discord.gg/vqBrcV7Nd) |[**Documents**](https://db-gpt.readthedocs.io/en/latest/)|[**Wechat**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC)|[**Community**](https://github.com/eosphoros-ai/community)
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
- [contract](#contact-information)

[DB-GPT Youtube Video](https://www.youtube.com/watch?v=f5_g0OObZBQ)

## Demo
Run on an RTX 4090 GPU.

![demo_en](https://github.com/eosphoros-ai/DB-GPT/assets/17919400/d40118e4-8e76-45b6-b4a6-30e5ff170f42)

#### Chat with data, and figure charts.

![db plugins demonstration](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/4113ac15-83c2-4350-86c0-5fc795677abd)

<p align="left">
  <img src="./assets/chat_excel/chat_excel_6.png" width="800px" />
</p>

<p align="left">
  <img src="./assets/chat_dashboard/chat_dashboard_2.png" width="800px" />
</p>


## Features

Currently, we have released multiple key features, which are listed below to demonstrate our current capabilities:
- SQL language capabilities
  - SQL generation
  - SQL diagnosis
- Private domain Q&A and data processing
  - Knowledge Management(We currently support many document formats: txt, pdf, md, html, doc, ppt, and url.)
- ChatDB
- ChatExcel
- ChatDashboard
- Multi-Agents&Plugins
- Unified vector storage/indexing of knowledge base
  - Support for unstructured data such as PDF, TXT, Markdown, CSV, DOC, PPT, and WebURL
- Multi LLMs Support, Supports multiple large language models, currently supporting
  - 🔥 InternLM(7b,20b)
  - 🔥 Baichuan2(7b,13b)
  - 🔥 Vicuna-v1.5(7b,13b)
  - 🔥 llama-2(7b,13b,70b)
  - WizardLM-v1.2(13b)
  - Vicuna (7b,13b)
  - ChatGLM-6b (int4,int8)
  - ChatGLM2-6b (int4,int8)
  - guanaco(7b,13b,33b)
  - Gorilla(7b,13b)
  - baichuan(7b,13b)


- Support API Proxy LLMs
  - [x] ChatGPT
  - [x] Tongyi
  - [x] Wenxin
  - [x] Spark
  - [x] MiniMax
  - [x] ChatGLM

## Introduction 
DB-GPT creates a vast model operating system using [FastChat](https://github.com/lm-sys/FastChat) and offers a large language model powered by vicuna. In addition, we provide private domain knowledge base question-answering capability. Furthermore, we also provide support for additional plugins, and our design natively supports the Auto-GPT plugin.Our vision is to make it easier and more convenient to build  applications around databases and llm.

Is the architecture of the entire DB-GPT shown in the following figure:

<p align="center">
  <img src="./assets/DB-GPT.png" width="800" />
</p>

The core capabilities mainly consist of the following parts:
1. Knowledge base capability: Supports private domain knowledge base question-answering capability.
2. Large-scale model management capability: Provides a large model operating environment based on FastChat.
3. Unified data vector storage and indexing: Provides a uniform way to store and index various data types.
4. Connection module: Used to connect different modules and data sources to achieve data flow and interaction.
5. Agent and plugins: Provides Agent and plugin mechanisms, allowing users to customize and enhance the system's behavior.
6. Prompt generation and optimization: Automatically generates high-quality prompts and optimizes them to improve system response efficiency.
7. Multi-platform product interface: Supports various client products, such as web, mobile applications, and desktop applications.

### SubModule
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) Text-to-SQL parsing with LLMs
- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT Plugins, Can run autogpt plugin directly
- [DB-GPT-Web](https://github.com/eosphoros-ai/DB-GPT-Web)  ChatUI for DB-GPT  

## Image
🌐 [AutoDL Image](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)

## Install 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**Quickstart**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html)

### Language Switching
    In the .env configuration file, modify the LANGUAGE parameter to switch to different languages. The default is English (Chinese: zh, English: en, other languages to be added later).

## Contribution

- Please run `black .` before submitting the code. contributing guidelines, [how to contribution](https://github.com/csunny/DB-GPT/blob/main/CONTRIBUTING.md)

## RoadMap

<p align="left">
  <img src="./assets/roadmap.jpg" width="800px" />
</p>

### KBQA RAG optimization
- [] KnownledgeGraph

### Multi Datasource Support
| DataSource                                                                      | support     | Notes                                       |
| ------------------------------------------------------------------------------  | ----------- | ------------------------------------------- |
| [MySQL](https://www.mysql.com/)                                                 | Yes         |                                             |
| [PostgresSQL](https://www.postgresql.org/)                                      | Yes         |                                             |
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

### Multi-Models And vLLM
- [meta-llama/Llama-2-7b-chat-hf](https://huggingface.co/meta-llama/Llama-2-7b-chat-hf)
- [baichuan2-7b/baichuan2-13b](https://huggingface.co/baichuan-inc)
- [internlm/internlm-chat-7b](https://huggingface.co/internlm/internlm-chat-7b)
- [Qwen/Qwen-7B-Chat/Qwen-14B-Chat](https://huggingface.co/Qwen/)
- [Vicuna](https://huggingface.co/Tribbiani/vicuna-13b)
- [BlinkDL/RWKV-4-Raven](https://huggingface.co/BlinkDL/rwkv-4-raven)
- [camel-ai/CAMEL-13B-Combined-Data](https://huggingface.co/camel-ai/CAMEL-13B-Combined-Data)
- [databricks/dolly-v2-12b](https://huggingface.co/databricks/dolly-v2-12b)
- [FreedomIntelligence/phoenix-inst-chat-7b](https://huggingface.co/FreedomIntelligence/phoenix-inst-chat-7b)
- [h2oai/h2ogpt-gm-oasst1-en-2048-open-llama-7b](https://huggingface.co/h2oai/h2ogpt-gm-oasst1-en-2048-open-llama-7b)
- [lcw99/polyglot-ko-12.8b-chang-instruct-chat](https://huggingface.co/lcw99/polyglot-ko-12.8b-chang-instruct-chat)
- [lmsys/fastchat-t5-3b-v1.0](https://huggingface.co/lmsys/fastchat-t5)
- [mosaicml/mpt-7b-chat](https://huggingface.co/mosaicml/mpt-7b-chat)
- [Neutralzz/BiLLa-7B-SFT](https://huggingface.co/Neutralzz/BiLLa-7B-SFT)
- [nomic-ai/gpt4all-13b-snoozy](https://huggingface.co/nomic-ai/gpt4all-13b-snoozy)
- [NousResearch/Nous-Hermes-13b](https://huggingface.co/NousResearch/Nous-Hermes-13b)
- [openaccess-ai-collective/manticore-13b-chat-pyg](https://huggingface.co/openaccess-ai-collective/manticore-13b-chat-pyg)
- [OpenAssistant/oasst-sft-4-pythia-12b-epoch-3.5](https://huggingface.co/OpenAssistant/oasst-sft-4-pythia-12b-epoch-3.5)
- [project-baize/baize-v2-7b](https://huggingface.co/project-baize/baize-v2-7b)
- [Salesforce/codet5p-6b](https://huggingface.co/Salesforce/codet5p-6b)
- [StabilityAI/stablelm-tuned-alpha-7b](https://huggingface.co/stabilityai/stablelm-tuned-alpha-7b)
- [THUDM/chatglm-6b](https://huggingface.co/THUDM/chatglm-6b)
- [THUDM/chatglm2-6b](https://huggingface.co/THUDM/chatglm2-6b)
- [tiiuae/falcon-40b](https://huggingface.co/tiiuae/falcon-40b)
- [timdettmers/guanaco-33b-merged](https://huggingface.co/timdettmers/guanaco-33b-merged)
- [togethercomputer/RedPajama-INCITE-7B-Chat](https://huggingface.co/togethercomputer/RedPajama-INCITE-7B-Chat)
- [WizardLM/WizardLM-13B-V1.0](https://huggingface.co/WizardLM/WizardLM-13B-V1.0)
- [WizardLM/WizardCoder-15B-V1.0](https://huggingface.co/WizardLM/WizardCoder-15B-V1.0)
- [baichuan-inc/baichuan-7B](https://huggingface.co/baichuan-inc/baichuan-7B)
- [HuggingFaceH4/starchat-beta](https://huggingface.co/HuggingFaceH4/starchat-beta)
- [FlagAlpha/Llama2-Chinese-13b-Chat](https://huggingface.co/FlagAlpha/Llama2-Chinese-13b-Chat)
- [BAAI/AquilaChat-7B](https://huggingface.co/BAAI/AquilaChat-7B)
- [all models of OpenOrca](https://huggingface.co/Open-Orca)
- [Spicyboros](https://huggingface.co/jondurbin/spicyboros-7b-2.2?not-for-all-audiences=true) + [airoboros 2.2](https://huggingface.co/jondurbin/airoboros-l2-13b-2.2)
- [VMware&#39;s OpenLLaMa OpenInstruct](https://huggingface.co/VMware/open-llama-7b-open-instruct)

### Agents market and Plugins
- multi-agents framework
- custom plugin development 
- plugin market

### Text2SQL Finetune

| LLMs                                                     | Size                        | Module            | Template |
| -------------------------------------------------------- | --------------------------- | ----------------- |----------|
| [LLaMA](https://github.com/facebookresearch/llama)       | 7B/13B/33B/65B              | q_proj,v_proj     | -        |
| [LLaMA-2](https://huggingface.co/meta-llama)             | 7B/13B/70B                  | q_proj,v_proj     | llama2   |
| [BLOOM](https://huggingface.co/bigscience/bloom)         | 560M/1.1B/1.7B/3B/7.1B/176B | query_key_value   | -        |
| [BLOOMZ](https://huggingface.co/bigscience/bloomz)       | 560M/1.1B/1.7B/3B/7.1B/176B | query_key_value   | -        |
| [Falcon](https://huggingface.co/tiiuae/falcon-7b)        | 7B/40B                      | query_key_value   | -        |
| [Baichuan](https://github.com/baichuan-inc/baichuan-13B) | 7B/13B                      | W_pack            | baichuan |
| [Baichuan2](https://github.com/baichuan-inc/Baichuan2)   | 7B/13B                      | W_pack            | baichuan2 |
| [InternLM](https://github.com/InternLM/InternLM)         | 7B                          | q_proj,v_proj     | intern   |
| [Qwen](https://github.com/QwenLM/Qwen-7B)                | 7B                          | c_attn            | chatml   |
| [XVERSE](https://github.com/xverse-ai/XVERSE-13B)        | 13B                         | q_proj,v_proj     | xverse   |
| [ChatGLM2](https://github.com/THUDM/ChatGLM2-6B)         | 6B                          | query_key_value   | chatglm2 |


Datasets
| Datasets               | License      | Link                                                                                                                 |
| ---------------------- | ------------ | -------------------------------------------------------------------------------------------------------------------- |
| academic               | Not Found    | [https://github.com/jkkummerfeld/text2sql-data](https://github.com/jkkummerfeld/text2sql-data)                       |
| advising               | CC-BY-4.0    | [https://github.com/jkkummerfeld/text2sql-data](https://github.com/jkkummerfeld/text2sql-data)                       |
| atis                   | Not Found    | [https://github.com/jkkummerfeld/text2sql-data](https://github.com/jkkummerfeld/text2sql-data)                       |
| restaurants            | Not Found    | [https://github.com/jkkummerfeld/text2sql-data](https://github.com/jkkummerfeld/text2sql-data)                       |
| scholar                | Not Found    | [https://github.com/jkkummerfeld/text2sql-data](https://github.com/jkkummerfeld/text2sql-data)                       |
| imdb                   | Not Found    | [https://github.com/jkkummerfeld/text2sql-data](https://github.com/jkkummerfeld/text2sql-data)                       |
| yelp                   | Not Found    | [https://github.com/jkkummerfeld/text2sql-data](https://github.com/jkkummerfeld/text2sql-data)                       |
| criteria2sql           | Apache-2.0   | [https://github.com/xiaojingyu92/Criteria2SQL](https://github.com/xiaojingyu92/Criteria2SQL)                         |
| css                    | CC-BY-4.0    | [https://huggingface.co/datasets/zhanghanchong/css](https://huggingface.co/datasets/zhanghanchong/css)               |
| eICU                   | CC-BY-4.0    | [https://github.com/glee4810/EHRSQL](https://github.com/glee4810/EHRSQL)                                             |
| mimic_iii              | CC-BY-4.0    | [https://github.com/glee4810/EHRSQL](https://github.com/glee4810/EHRSQL)                                             |
| geonucleardata         | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| greatermanchestercrime | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| studentmathscore       | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| thehistoryofbaseball   | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| uswildfires            | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| whatcdhiphop           | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| worldsoccerdatabase    | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| pesticide              | CC-BY-SA-4.0 | [https://github.com/chiahsuan156/KaggleDBQA](https://github.com/chiahsuan156/KaggleDBQA)                             |
| mimicsql_data          | MIT          | [https://github.com/wangpinggl/TREQS](https://github.com/wangpinggl/TREQS)                                           |
| nvbench                | MIT          | [https://github.com/TsinghuaDatabaseGroup/nvBench](https://github.com/TsinghuaDatabaseGroup/nvBench)                 |
| sede                   | Apache-2.0   | [https://github.com/hirupert/sede](https://github.com/hirupert/sede)                                                 |
| spider                 | CC-BY-SA-4.0 | [https://huggingface.co/datasets/spider](https://huggingface.co/datasets/spider)                                     |
| sql_create_context     | CC-BY-4.0    | [https://huggingface.co/datasets/b-mc2/sql-create-context](https://huggingface.co/datasets/b-mc2/sql-create-context) |
| squall                 | CC-BY-SA-4.0 | [https://github.com/tzshi/squall](https://github.com/tzshi/squall)                                                   |
| wikisql                | BSD 3-Clause | [https://github.com/salesforce/WikiSQL](https://github.com/salesforce/WikiSQL)                                       |
| BIRD                | Not Found | https://bird-bench.github.io/                                       |
| CHASE                | MIT LICENSE | https://xjtu-intsoft.github.io/chase/   |  
| cosql                | Not Found | https://yale-lily.github.io/cosql/   |


[More Information about Text2SQL finetune](https://github.com/eosphoros-ai/DB-GPT-Hub)

## Licence

The MIT License (MIT)

## Contact Information
We are working on building a community, if you have any ideas about building the community, feel free to contact us.
[![](https://dcbadge.vercel.app/api/server/vqBrcV7Nd?compact=true&style=flat)](https://discord.gg/vqBrcV7Nd)

<p align="center">
  <img src="./assets/wechat.jpg" width="300px" />
</p>

[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
