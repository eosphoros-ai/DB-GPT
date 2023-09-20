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
    <a href="https://discord.gg/FMGwbRQrM">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/FMGwbRQrM?compact=true&style=flat" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[**简体中文**](README.zh.md) |[**Discord**](https://discord.gg/FMGwbRQrM) |[**Documents**](https://db-gpt.readthedocs.io/en/latest/)|[**Wechat**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC)|[**Community**](https://github.com/eosphoros-ai/community)
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

## Licence

The MIT License (MIT)

## Contact Information
We are working on building a community, if you have any ideas about building the community, feel free to contact us.
[![](https://dcbadge.vercel.app/api/server/FMGwbRQrM?compact=true&style=flat)](https://discord.gg/FMGwbRQrM)

<p align="center">
  <img src="./assets/wechat.jpg" width="300px" />
</p>

[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
