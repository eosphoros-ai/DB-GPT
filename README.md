# DB-GPT ![GitHub Repo stars](https://img.shields.io/github/stars/csunny/db-gpt?style=social)

---

[English Edition](README.en.md)

专注于数据库垂直领域的 GPT 项目，提供大模型与数据的本地化使用方案，保障数据的隐私安全，适用企业内和个人。

## 特性一览

- SQL 语言能力
  - SQL生成
  - SQL诊断
- 私域问答与数据处理
  - 数据库知识问答
  - 数据处理

## 架构方案

<p align="center">
  <img src="./asserts/DB-GPT.png" width="740px" />
</p>

DB-GPT 基于[FastChat](https://github.com/lm-sys/FastChat) 构建大模型运行环境，并提供 vicuna 作为基础的大语言模型。此外，我们通过 langchain 和 llama-index 提供私域知识库问答能力。 

## 效果演示

示例通过 RTX 4090 GPU 演示，[YouTube 地址](https://www.youtube.com/watch?v=1PWI6F89LPo)
### 运行环境演示

<p align="center">
  <img src="./asserts/演示.gif" width="680px" />
</p>

### SQL 生成

首先选择对应的数据库, 然后模型即可根据对应的数据库 Schema 信息生成 SQL。

<p align="center">
  <img src="./asserts/SQLGEN.png" width="680px" />
</p>

运行成功的效果如下面的演示：

<p align="center">
  <img src="./asserts/exeable.png" width="680px" />
</p>

### 数据库问答

<p align="center">
  <img src="./asserts/DB_QA.png" width="680px" />
</p>

基于默认内置知识库。

<p align="center">
  <img src="./asserts/VectorDBQA.png" width="680px" />
</p>

## 部署

### 1. 安装 Python 依赖的模块。

```bash
$ python>=3.9
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

```bash
$ cd pilot/server
$ python vicuna_server.py
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

|[<img src="https://avatars.githubusercontent.com/u/17919400?v=4" width="100px;"/><br/><sub><b>csunny</b></sub>](https://github.com/csunny)<br/>|
| :---: | :---: |


This project follows the git-contributor [spec](https://github.com/xudafeng/git-contributor), auto updated at `Sun May 14 2023 22:37:46 GMT+0800`.

<!-- GITCONTRIBUTOR_END -->

## Licence

The MIT License (MIT)
