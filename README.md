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

[DB-GPT](https://github.com/csunny/DB-GPT) is an experimental open-source application that builds upon the [FastChat](https://github.com/lm-sys/FastChat) model and uses vicuna as its base model. Additionally, it looks like this application incorporates langchain and llama-index embedding knowledge to improve Database-QA capabilities. 

Overall, it appears to be a sophisticated and innovative tool for working with databases. If you have any specific questions about how to use or implement DB-GPT in your work, please let me know and I'll do my best to assist you.


## 效果演示

Run on an RTX 4090 GPU (The origin mov not sped up!, [YouTube地址](https://www.youtube.com/watch?v=1PWI6F89LPo))
- 运行演示

![](https://github.com/csunny/DB-GPT/blob/main/asserts/演示.gif)


- SQL生成示例
首先选择对应的数据库, 然后模型即可根据对应的数据库Schema信息生成SQL

<img src="https://github.com/csunny/DB-GPT/blob/main/asserts/SQLGEN.png" width="600" margin-left="auto" margin-right="auto" >

The Generated SQL is runable.

<img src="https://github.com/csunny/DB-GPT/blob/main/asserts/exeable.png" width="600" margin-left="auto" margin-right="auto" >

- 数据库QA示例 

<img src="https://github.com/csunny/DB-GPT/blob/main/asserts/DB_QA.png" margin-left="auto" margin-right="auto" width="600">

基于默认内置知识库QA

<img src="https://github.com/csunny/DB-GPT/blob/main/asserts/VectorDBQA.png" width="600" margin-left="auto" margin-right="auto" >

# Dependencies
1. First you need to install python requirements.
```
python>=3.9
pip install -r requirements.txt
```
or if you use conda envirenment, you can use this command
```
cd DB-GPT
conda env create -f environment.yml
```

2. MySQL Install

In this project examples, we connect mysql and run SQL-Generate. so you need install mysql local for test. recommand docker
```
docker run --name=mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=aa12345678 -dit mysql:latest
```
The password just for test, you can change this if necessary

# Install
1. 基础模型下载
关于基础模型, 可以根据[vicuna](https://github.com/lm-sys/FastChat/blob/main/README.md#model-weights)合成教程进行合成。 
如果此步有困难的同学，也可以直接使用[Hugging Face](https://huggingface.co/)上的模型进行替代. [替代模型](https://huggingface.co/Tribbiani/vicuna-7b)

2. Run model server
```
cd pilot/server
python vicuna_server.py
```

3. Run gradio webui
```
python webserver.py 
```

4. 基于阿里云部署指南
[阿里云部署指南](https://open.oceanbase.com/blog/3278046208)

总的来说，它是一个用于数据库的复杂且创新的AI工具。如果您对如何在工作中使用或实施DB-GPT有任何具体问题，请联系我, 我会尽力提供帮助, 同时也欢迎大家参与到项目建设中, 做一些有趣的事情。

<img src="https://github.com/csunny/DB-GPT/blob/main/asserts/wechat.jpg" width="400" margin-left="auto" margin-right="auto" >

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


This project follows the git-contributor [spec](https://github.com/xudafeng/git-contributor), auto updated at `Sun May 14 2023 22:37:46 GMT+0800`.

<!-- GITCONTRIBUTOR_END -->

## Licence

The MIT License (MIT)
