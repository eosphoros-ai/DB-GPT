# DB-GPT: 用私有化LLM技术定义数据库下一代交互方式

<p align="left">
  <img src="./assets/LOGO.png" width="100%" />
</p>


<div align="center">
  <p>
    <a href="https://github.com/eosphoros-ai/DB-GPT">
        <img alt="stars" src="https://img.shields.io/github/stars/csunny/db-gpt?style=social" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT">
        <img alt="forks" src="https://img.shields.io/github/forks/csunny/db-gpt?style=social" />
    </a>
    <a href="https://opensource.org/licenses/MIT">
      <img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg" />
    </a>
     <a href="https://github.com/eosphoros-ai/DB-GPT/releases">
      <img alt="Release Notes" src="https://img.shields.io/github/release/csunny/DB-GPT" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT/issues">
      <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/csunny/DB-GPT" />
    </a>
    <a href="https://discord.gg/vqBrcV7Nd">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/vqBrcV7Nd?compact=true&style=flat" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>

[**English**](README.md)|[**Discord**](https://discord.gg/vqBrcV7Nd)|[**文档**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/)|[**微信**](https://github.com/csunny/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC)|[**社区**](https://github.com/eosphoros-ai/community)
</div>

## DB-GPT 是什么？

随着大模型的发布迭代，大模型变得越来越智能，在使用大模型的过程当中，遇到极大的数据安全与隐私挑战。在利用大模型能力的过程中我们的私密数据跟环境需要掌握自己的手里，完全可控，避免任何的数据隐私泄露以及安全风险。基于此，我们发起了DB-GPT项目，为所有以数据库为基础的场景，构建一套完整的私有大模型解决方案。 此方案因为支持本地部署，所以不仅仅可以应用于独立私有环境，而且还可以根据业务模块独立部署隔离，让大模型的能力绝对私有、安全、可控。我们的愿景是让围绕数据库构建大模型应用更简单，更方便。

DB-GPT 是一个开源的以数据库为基础的GPT实验项目，使用本地化的GPT大模型与您的数据和环境进行交互，无数据泄露风险，100% 私密



## 目录

- [安装](#安装)
- [效果演示](#效果演示)
- [架构方案](#架构方案)
- [特性简介](#特性一览)
- [贡献](#贡献)
- [路线图](#路线图)
- [联系我们](#联系我们)

[DB-GPT视频介绍](https://www.bilibili.com/video/BV1au41157bj/?spm_id_from=333.337.search-card.all.click&vd_source=7792e22c03b7da3c556a450eb42c8a0f)

## 效果演示

示例通过 RTX 4090 GPU 演示

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

#### 根据自然语言对话生成分析图表

<p align="left">
  <img src="./assets/chat_excel/chat_excel_6.png" width="800px" />
</p>

<p align="left">
  <img src="./assets/dashboard.png" width="800px" />
</p>

<p align="left">
  <img src="./assets/chat_dashboard/chat_dashboard_2.png" width="800px" />
</p>

## 安装

![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**教程**](https://db-gpt.readthedocs.io/en/latest/getting_started/install/deploy/deploy.html)
- [**安装**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/deploy/deploy.html)
  - [**Install Step by Step**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/deploy/deploy.html)
  - [**Docker安装**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/docker/docker.html)
  - [**Docker Compose安装**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/docker_compose/docker_compose.html)
- [**产品使用手册**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/application/chatdb/chatdb.html)
  - [**ChatData**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/application/chatdb/chatdb.html)
  - [**ChatKnowledge**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/application/kbqa/kbqa.html)
  - [**ChatExcel**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/application/chatexcel/chatexcel.html)
  - [**Dashboard**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/application/dashboard/dashboard.html)
  - [**LLM 管理**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/application/model/model.html)
  - [**Chat Agent**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/application/chatagent/chatagent.html)
- [**如何部署LLM**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/cluster/cluster.html)
  - [**Standalone**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/cluster/vms/standalone.html#)
  - [**Cluster**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/cluster/vms/index.html)
  - [**vLLM**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/install/llm/vllm/vllm.html)
- [**如何Debug**](https://db-gpt.readthedocs.io/en/latest/getting_started/observability.html)
- [**FAQ**](https://db-gpt.readthedocs.io/en/latest/getting_started/faq/deploy/deploy_faq.html)

## 特性一览

目前我们已经发布了多种关键的特性，这里一一列举展示一下当前发布的能力。

- 私域问答&数据处理
  支持内置、多文件格式上传、插件自抓取等方式自定义构建知识库，对海量结构化，非结构化数据做统一向量存储与检索
- 多数据源&可视化
  支持自然语言与Excel、数据库、数仓等多种数据源交互，并支持分析报告。
- 自动化微调
  围绕大语言模型、Text2SQL数据集、LoRA/QLoRA/Pturning等微调方法构建的自动化微调轻量框架, 让TextSQL微调像流水线一样方便。详见: [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub)
- Multi-Agents&Plugins
  支持自定义插件执行任务，原生支持Auto-GPT插件模型，Agents协议采用Agent Protocol标准
- 多模型支持与管理
  海量模型支持，包括开源、API代理等几十种大语言模型。如LLaMA/LLaMA2、Baichuan、ChatGLM、文心、通义、智谱等。
  - 支持多种大语言模型, 当前已支持如下模型: 
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
  - 支持在线代理模型 
    - [x] [ChatGPT](https://api.openai.com/)
    - [x] [Tongyi](https://www.aliyun.com/product/dashscope)
    - [x] [Wenxin](https://cloud.baidu.com/product/wenxinworkshop?track=dingbutonglan)
    - [x] [ChatGLM](http://open.bigmodel.cn/)

- 支持数据源

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

## 架构方案
DB-GPT基于 [FastChat](https://github.com/lm-sys/FastChat) 构建大模型运行环境。此外，我们通过LangChain提供私域知识库问答能力。同时我们支持插件模式, 在设计上原生支持Auto-GPT插件。我们的愿景是让围绕数据库和LLM构建应用程序更加简便和便捷。

整个DB-GPT的架构，如下图所示

<p align="center">
  <img src="./assets/DB-GPT_zh.png" width="800px" />
</p>

核心能力主要有以下几个部分。 
1. 多模型：支持多LLM，如LLaMA/LLaMA2、CodeLLaMA、ChatGLM、QWen、Vicuna以及代理模型ChatGPT、Baichuan、tongyi、wenxin等
2. 私域知识库问答: 可以根据本地文档（如pdf、word、excel等数据）进行高质量的智能问答。
3. 统一数据向量存储和索引: 将数据嵌入为向量并存储在向量数据库中，提供内容相似性搜索。  
4. 多数据源: 用于连接不同的模块和数据源，实现数据的流动和交互。
5. Agent与插件: 提供Agent和插件机制，使得用户可以自定义并增强系统的行为。  
6. 隐私和安全: 您可以放心，没有数据泄露的风险，您的数据100%私密和安全。
7. Text2SQL: 我们通过在大型语言模型监督微调（SFT）来增强文本到SQL的性能

### 子模块
- [DB-GPT-Hub](https://github.com/csunny/DB-GPT-Hub) 通过微调来持续提升Text2SQL效果 
- [DB-GPT-Plugins](https://github.com/csunny/DB-GPT-Plugins) DB-GPT 插件仓库, 兼容Auto-GPT
- [DB-GPT-Web](https://github.com/csunny/DB-GPT-Web)  多端交互前端界面

## Image

🌐 [AutoDL镜像](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)

🌐 [阿里云镜像](http://dbgpt.site/web/#/p/dc4bb97e0bc15302dbf3a5d5571142dd)


### 多语言切换

在.env 配置文件当中，修改LANGUAGE参数来切换使用不同的语言，默认是英文(中文zh, 英文en, 其他语言待补充)

## 使用说明

### 多模型使用

[使用指南](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/modules/llms.html)

# 贡献
> 提交代码前请先执行 `black .`

这是一个用于数据库的复杂且创新的工具, 我们的项目也在紧急的开发当中, 会陆续发布一些新的feature。如在使用当中有任何具体问题, 优先在项目下提issue, 如有需要, 请联系如下微信，我会尽力提供帮助，同时也非常欢迎大家参与到项目建设中。

## Licence

The MIT License (MIT)

# 路线图

<p align="left">
  <img src="./assets/roadmap.jpg" width="800px" />
</p>

### 知识库RAG检索优化

- [x] Multi Documents
  - [x] PDF
  - [x] Excel, csv
  - [x] Word
  - [x] Text
  - [x] MarkDown
  - [ ] Code
  - [ ] Images 
- [x] RAG
- [ ] Graph Database
  - [ ] Neo4j Graph
  - [ ] Nebula Graph
- [x] Multi Vector Database
  - [x] Chroma
  - [x] Milvus
  - [x] Weaviate
  - [x] PGVector
  - [ ] Elasticsearch
  - [ ] ClickHouse
  - [ ] Faiss 

### 多数据源支持

- 支持数据源

  - [x] MySQL
  - [x] PostgresSQL
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

### 多模型管理与推理优化
- [x] [集群部署](https://db-gpt.readthedocs.io/en/latest/getting_started/install/cluster/vms/index.html)
- [x] [fastchat支持](https://github.com/lm-sys/FastChat)
- [x] [fastchat支持](https://github.com/lm-sys/FastChat)
- [x] [vLLM 支持](https://db-gpt.readthedocs.io/en/latest/getting_started/install/llm/vllm/vllm.html)
- [ ] 云原生环境与Ray环境支持
- [ ] 注册中心引入nacos
- [ ] 上层接口兼容Openai
- [ ] Embedding模型扩充，优化

### Agents与插件市场
- [x] 多Agents框架
- [x] 自定义Agents
- [ ] 插件市场
- [ ] CoT集成
- [ ] 丰富插件样本库
- [ ] 支持AutoGPT协议
- [ ] Multi-agents & 可视化能力打通，定义LLM+Vis新标准


### 测试评估能力建设
- [ ] 知识库的数据文本集
- [ ] 问题集合 [easy、medium、hard]
- [ ] 评分机制
- [ ] Excel + DB库表的测试评估

### 成本与可观测性 
- [x] [debugging](https://db-gpt.readthedocs.io/en/latest/getting_started/observability.html)
- [ ] 可观测性
- [ ] 推理预算

### Text2SQL微调
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

-  SFT模型准确率 
截止20231010，我们利用本项目基于开源的13B大小的模型微调后，在Spider的评估集上的执行准确率，已经超越GPT-4!

| 模型名称                           | 执行准确率           | 说明                                                                                                                      |
| ----------------------------------| ------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| **GPT-4**                         | **0.762**          | [numbersstation-eval-res](https://www.numbersstation.ai/post/nsql-llama-2-7b)                                                  |
| ChatGPT                           | 0.728              | [numbersstation-eval-res](https://www.numbersstation.ai/post/nsql-llama-2-7b)                                                  | 
| **CodeLlama-13b-Instruct-hf_lora**| **0.789**          | sft train by our this project,only used spider train dataset ,the same eval  way in this project  with lora SFT                |
| CodeLlama-13b-Instruct-hf_qlora   | 0.774              | sft train by our this project,only used spider train dataset ,the same eval  way in this project  with qlora and nf4,bit4 SFT  |
| wizardcoder                       | 0.610              | [text-to-sql-wizardcoder](https://github.com/cuplv/text-to-sql-wizardcoder/tree/main)                                          |  
| CodeLlama-13b-Instruct-hf         | 0.556              | eval in this project default param                                                                                             |
| llama2_13b_hf_lora_best           | 0.744              | sft train by our this project,only used spider train dataset ,the same eval  way in this project                               |

[More Information about Text2SQL finetune](https://github.com/eosphoros-ai/DB-GPT-Hub)

## 联系我们

<p align="center">
  <img src="./assets/wechat.jpg" width="300px" />
</p>


[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
