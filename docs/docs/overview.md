---
sidebar_position: 0
---

# Overview
DB-GPT is an **open-source framework for large language models(LLMs) in the databases fields**. It's purpose is to build infrastructure for the domain of large language models, making it easier and more convenient to develop applications around databases by developing various technical capabilities such as:

-  **SMMF(Service-oriented Multi-model Management Framework)**
-  **Text2SQL Fine-tuning**
-  **RAG(Retrieval Augmented Generation) Framework and Optimization**
-  **Data-Driven Agents Framework Collaboration**

In the Data 3.0 era, enterprises/developers can build their own exclusive applications with less code based on LLMs and databases.

<p align="left">
  <img src={'/img/dbgpt.png'} width="680px" />
</p>


## Features

##### Private Domain Q&A & Data Processing & RAG
- Supports custom construction of knowledge bases through methods such as built-in, multi-file format uploads, and plugin-based web scraping. Enables unified vector storage and retrieval of massive structured and unstructured data.

##### Multi-Data Source & GBI(Generative Business Intelligence)
- Supports interaction between natural language and various data sources such as Excel, databases, and data warehouses. Also supports analysis reporting. 

##### SMMF(Service-oriented Multi-model Management Framework)
- Supports a wide range of models, including dozens of large language models such as open-source models and API proxies. Examples include LLaMA/LLaMA2, Baichuan, ChatGLM, ERNIE Bot, Qwen, Spark, etc.

##### Automated Fine-tuning
- Supports Text2SQL fine-tuning. Provides a lightweight automatic fine-tuning framework around the fields of LLM and Text2SQL, supporting methods such as LoRA/QLoRA/P-turning, making Text2SQL fine-tuning as convenient as a production line.
##### Data-Driven Multi-Agents & Plugins
- Supports executing tasks through custom plugins and natively supports the Auto-GPT plugin model. [Agents protocol](https://agentprotocol.ai/) follows the Agent Protocol standard.

##### Privacy and Security
- Supports data privacy protection. Ensures data privacy and security through techniques such as privatizing large language models and proxy de-identification.

## Getting Started

 - [Quickstart](/docs/quickstart)
 - [Installation](/docs/installation)


## Terminology

| terminology          | Description                                                   |
|----------------------|---------------------------------------------------------------|
| <center> `DB-GPT`       </center>| DataBase Generative Pre-trained Transformer, an open source framework around databases and large language models |
| <center> `Text2SQL/NL2SQL`  </center>  | Text to SQL uses large language model capabilities to generate SQL statements based on natural language, or provide explanations based on SQL statements |
| <center>`KBQA`   </center>  | Knowledge-Based Q&A system |
| <center>`GBI`            </center>  | Generative Business Intelligence, based on large language models and data analysis, provides business intelligence analysis and decision-making through dialogue |
| <center>`LLMOps`   </center>  | A large language model operation framework that provides a standard end-to-end workflow for training, tuning, deploying, and monitoring LLM to accelerate application deployment of generated AI models |
|<center> `Embedding`  </center>   | Methods to convert text, audio, video and other materials into vectors |
|<center> `RAG`   </center>| Retrieval Augmented Generation |

## Use Cases

- [Use Cases](/docs/use_cases)

## Modules

#### [SMMF](/docs/modules/smmf)
Service-oriented Multi-model Management Framework 

#### [Retrieval](/docs/modules/rag)
Multi-Knowledge Enhanced Retrieval-Augmented Generation Framework

#### [Agents](/docs/modules/agent)
Data Driven Multi-Agents

#### [Fine-tuning](/docs/modules/fine_tuning)
Fine-tuning module for Text2SQL/Text2DSL


## More

- [Connections](/docs/modules/connections) 
Connect various data sources

- [Obvervablity](/docs/operation/advanced_tutorial/debugging)
Observing & monitoring

- [Evaluation](/docs/modules/eval)
Evaluate framework performance and accuracy