# DB-GPT ![GitHub Repo stars](https://img.shields.io/github/stars/csunny/db-gpt?style=social)

---
[English Edition](README.en.md)

## 背景
随着大模型的发布迭代，大模型变得越来越智能，我们在使用大模型的过程当中，遇到极大的数据安全与隐私挑战。在利用大模型能力的过程中我们的私密数据跟环境需要掌握自己的手里，完全可控，避免任何的数据隐私泄露以及安全风险。基于此，我们发起了DB-GPT项目，为所有以数据库为基础的场景，构建一套完整的私有大模型解决方案。 此方案因为支持本地部署，所以我们不仅仅可以应用于独立私有环境，而且还可以根据业务模块独立部署隔离，让大模型的能力绝对私有、安全、可控。

## 愿景
DB-GPT 是一个开源的以数据为基础的GPT实验项目，使用本地化的GPT大模型与您的数据和环境进行交互，无数据泄露风险，100% 私密，100% 安全。

## 特性一览

目前我们已经发布了多种关键的特性，这里我们一一列举展示一下我们当前发布的能力。
- SQL 语言能力
  - SQL生成
  - SQL诊断
- 私域问答与数据处理
  - 数据库知识问答
  - 数据处理
- 插件模型
  - 支持自定义插件执行任务，原生支持Auto-GPT插件。如:
    - SQL自动执行，获取查询结果
    - 自动爬取学习知识
- 知识库统一向量存储/索引
  - 非结构化数据支持
  - PDF、MarkDown、CSV、WebURL

## 架构方案

<p align="center">
  <img src="./assets/DB-GPT.png" width="600px" />
</p>


DB-GPT基于[FastChat](https://github.com/lm-sys/FastChat) 构建大模型运行环境，并提供 vicuna 作为基础的大语言模型。此外，我们通过 langchain提供私域知识库问答能力。同时我们支持插件模式, 在设计上原生支持Auto-GPT插件。 

## 效果演示

示例通过 RTX 4090 GPU 演示，[YouTube 地址](https://www.youtube.com/watch?v=1PWI6F89LPo)
### 运行环境演示

<p align="center">
  <img src="./assets/演示.gif" width="600px" />
</p>

### SQL 生成

首先选择对应的数据库, 然后模型即可根据对应的数据库 Schema 信息生成 SQL。

<p align="center">
  <img src="./assets/SQLGEN.png" width="600px" />
</p>

运行成功的效果如下面的演示：

<p align="center">
  <img src="./assets/exeable.png" width="600px" />
</p>

### 数据库问答

<p align="center">
  <img src="./assets/DB_QA.png" width="600px" />
</p>

基于默认内置知识库。

# Dependencies
1. First you need to install python requirements.
```
python>=3.10
pip install -r requirements.txt
```
or if you use conda envirenment, you can use this command
```
cd DB-GPT
conda env create -f environment.yml

<p align="center">
  <img src="./assets/VectorDBQA.png" width="600px" />
</p>

## 部署

### 1. 安装 Python

```bash
$ python>=3.10
$ pip install -r requirements.txt
```

或者直接使用 conda 环境

```bash
$ conda env create -f environment.yml
```

### 2. 安装 MySQL

本项目依赖一个本地的 MySQL 数据库服务，你需要本地安装，推荐直接使用 Docker 安装。

```bash
$ docker run --name=mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=aa12345678 -dit mysql:latest
```

### 3. 运行大模型

关于基础模型, 可以根据[vicuna](https://github.com/lm-sys/FastChat/blob/main/README.md#model-weights)合成教程进行合成。 
如果此步有困难的同学，也可以直接使用[Hugging Face](https://huggingface.co/)上的模型进行替代. [替代模型](https://huggingface.co/Tribbiani/vicuna-7b)

2. Run model server
```
cd pilot/server
python llmserver.py
```

运行 gradio webui

```bash
$ python webserver.py 
```

可以通过阿里云部署大模型，请参考[阿里云部署指南](https://open.oceanbase.com/blog/3278046208)。

## 感谢

项目取得的成果，需要感谢技术社区，尤其以下项目。

- [FastChat](https://github.com/lm-sys/FastChat) 提供 chat 服务
- [vicuna-13b](https://huggingface.co/Tribbiani/vicuna-13b) 作为基础模型
- [langchain](https://github.com/hwchase17/langchain) 工具链
- [llama-index](https://github.com/jerryjliu/llama_index) 基于现有知识库进行[In-Context Learning](https://arxiv.org/abs/2301.00234)来对其进行数据库相关知识的增强。

<!-- GITCONTRIBUTOR_START -->

## Contributors

|[<img src="https://avatars.githubusercontent.com/u/17919400?v=4" width="100px;"/><br/><sub><b>csunny</b></sub>](https://github.com/csunny)<br/>|[<img src="https://avatars.githubusercontent.com/u/1011681?v=4" width="100px;"/><br/><sub><b>xudafeng</b></sub>](https://github.com/xudafeng)<br/>|
| :---: | :---: |


This project follows the git-contributor [spec](https://github.com/xudafeng/git-contributor), auto updated at `Sun May 14 2023 23:02:43 GMT+0800`.

<!-- GITCONTRIBUTOR_END -->

这是一个用于数据库的复杂且创新的工具，如有任何具体问题，请联系如下微信，我会尽力提供帮助，同时也欢迎参与到项目建设中。

<p align="center">
  <img src="./assets/wechat.jpg" width="320px" />
</p>

## Licence

The MIT License (MIT)
