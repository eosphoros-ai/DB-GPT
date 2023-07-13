# DB-GPT: 用私有化LLM技术定义数据库下一代交互方式
<div align="center">
  <p>
    <a href="https://github.com/csunny/DB-GPT">
        <img alt="stars" src="https://img.shields.io/github/stars/csunny/db-gpt?style=social" />
    </a>
    <a href="https://github.com/csunny/DB-GPT">
        <img alt="forks" src="https://img.shields.io/github/forks/csunny/db-gpt?style=social" />
    </a>
  </p>

[**English**](README.md)|[**Discord**](https://discord.com/invite/EUEBmdpd) |[**Documents**](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/)|[**微信**](https://github.com/csunny/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC)
</div>


## DB-GPT 是什么？

随着大模型的发布迭代，大模型变得越来越智能，在使用大模型的过程当中，遇到极大的数据安全与隐私挑战。在利用大模型能力的过程中我们的私密数据跟环境需要掌握自己的手里，完全可控，避免任何的数据隐私泄露以及安全风险。基于此，我们发起了DB-GPT项目，为所有以数据库为基础的场景，构建一套完整的私有大模型解决方案。 此方案因为支持本地部署，所以不仅仅可以应用于独立私有环境，而且还可以根据业务模块独立部署隔离，让大模型的能力绝对私有、安全、可控。我们的愿景是让围绕数据库构建大模型应用更简单，更方便。

DB-GPT 是一个开源的以数据库为基础的GPT实验项目，使用本地化的GPT大模型与您的数据和环境进行交互，无数据泄露风险，100% 私密

[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT)](https://star-history.com/#csunny/DB-GPT)


[DB-GPT视频介绍](https://www.bilibili.com/video/BV1SM4y1a7Nj/?buvid=551b023900b290f9497610b2155a2668&is_story_h5=false&mid=%2BVyE%2Fwau5woPcUKieCWS0A%3D%3D&p=1&plat_id=116&share_from=ugc&share_medium=iphone&share_plat=ios&share_session_id=5D08B533-82A4-4D40-9615-7826065B4574&share_source=GENERIC&share_tag=s_i&timestamp=1686307943&unique_k=bhO3lgQ&up_id=31375446)  


## 效果演示

示例通过 RTX 4090 GPU 演示


https://github.com/csunny/DB-GPT/assets/13723926/55f31781-1d49-4757-b96e-7ef6d3dbcf80

#### 根据自然语言对话生成分析图表

<p align="left">
  <img src="./assets/dashboard.png" width="800px" />
</p>


#### 根据自然语言对话生成SQL
<p align="left">
  <img src="./assets/chatSQL.png" width="800px" />
</p>

#### 与数据库元数据信息进行对话, 生成准确SQL语句
<p align="left">
  <img src="./assets/chatdb.png" width="800px" />
</p>


#### 与数据对话, 直接查看执行结果
<p align="left">
  <img src="./assets/chatdata.png" width="800px" />
</p>

#### 知识库管理
<p align="left">
  <img src="./assets/ks.png" width="800px" />
</p>

#### 根据知识库对话, 比如pdf、csv、txt、words等等.
<p align="left">
  <img src="./assets/chat_knowledge.png" width="800px" />
</p>

## 最新发布
- [2023/07/12]🔥🔥🔥DB-GPT Python API 0.3.0 and Multi GPU Support. [documents](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/installation.html)
- [2023/07/06]🔥🔥🔥 全新的DB-GPT产品。 [使用文档](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/getting_started.html)
- [2023/06/25]🔥 支持ChatGLM2-6B模型。 [使用文档](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/modules/llms.html)
- [2023/06/14]🔥 支持gpt4all模型，可以在M1/M2 或者CPU机器上运行。 [使用文档](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/modules/llms.html)
- [2023/06/01]🔥 在Vicuna-13B基础模型的基础上，通过插件实现任务链调用。例如单句创建数据库的实现.
- [2023/06/01]🔥 QLoRA guanaco(原驼)支持, 支持4090运行33B
- [2023/05/28]🔥根据URL进行对话 [演示](./assets/chat_url_zh.gif)
- [2023/05/21] SQL生成与自动执行. [演示](./assets/auto_sql.gif)
- [2023/05/15] 知识库对话 [演示](./assets/new_knownledge.gif)
- [2023/05/06] SQL生成与诊断 [演示](./assets/演示.gif)

## 特性一览

目前我们已经发布了多种关键的特性，这里一一列举展示一下当前发布的能力。
- SQL 语言能力
  - SQL生成
  - SQL诊断
- 私域问答与数据处理
  - 知识库管理(目前支持 txt, pdf, md, html, doc, ppt, and url)
  - 数据库知识问答
  - 数据处理
- 插件模型
  - 支持自定义插件执行任务，原生支持Auto-GPT插件。如:
    - SQL自动执行，获取查询结果
    - 自动爬取学习知识
- 知识库统一向量存储/索引
  - 非结构化数据支持包括PDF、MarkDown、CSV、WebURL

- 多模型支持
  - 支持多种大语言模型, 当前已支持Vicuna(7b,13b), ChatGLM-6b(int4, int8), guanaco(7b,13b,33b), Gorilla(7b,13b)
  - TODO: codet5p, codegen2


## 架构方案
DB-GPT基于 [FastChat](https://github.com/lm-sys/FastChat) 构建大模型运行环境，并提供 vicuna 作为基础的大语言模型。此外，我们通过LangChain提供私域知识库问答能力。同时我们支持插件模式, 在设计上原生支持Auto-GPT插件。我们的愿景是让围绕数据库和LLM构建应用程序更加简便和便捷。

整个DB-GPT的架构，如下图所示

<p align="center">
  <img src="./assets/DB-GPT.png" width="800px" />
</p>

核心能力主要有以下几个部分。 
1. 知识库能力：支持私域知识库问答能力   
2. 大模型管理能力：基于FastChat提供一个大模型的运营环境。
3. 统一的数据向量化存储与索引：提供一种统一的方式来存储和索引各种数据类型。   
4. 连接模块：用于连接不同的模块和数据源，实现数据的流转和交互。 
5. Agent与插件：提供Agent和插件机制，使得用户可以自定义并增强系统的行为。  
6. Prompt自动生成与优化：自动化生成高质量的Prompt，并进行优化，提高系统的响应效率。  
7. 多端产品界面：支持多种不同的客户端产品，例如Web、移动应用和桌面应用等。

## 安装
[快速开始](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/getting_started/getting_started.html)

### 多语言切换
  在.env 配置文件当中，修改LANGUAGE参数来切换使用不同的语言，默认是英文(中文zh, 英文en, 其他语言待补充)

## 使用说明

### 多模型使用
  [使用指南](https://db-gpt.readthedocs.io/projects/db-gpt-docs-zh-cn/zh_CN/latest/modules/llms.html)


如果在使用知识库时遇到与nltk相关的错误，您需要安装nltk工具包。更多详情，请参见：[nltk文档](https://www.nltk.org/data.html)
Run the Python interpreter and type the commands:
```bash
>>> import nltk
>>> nltk.download()
```

我们提供了全新的的用户界面，可以通过我们的用户界面使用DB-GPT， 同时关于我们项目相关的一些代码跟原理介绍，我们也准备了以下几篇参考文章。
1.  [大模型实战系列(1) —— 强强联合Langchain-Vicuna应用实战](https://zhuanlan.zhihu.com/p/628750042)
2.  [大模型实战系列(2) —— DB-GPT 阿里云部署指南](https://zhuanlan.zhihu.com/p/629467580)
3.  [大模型实战系列(3) —— DB-GPT插件模型原理与使用](https://zhuanlan.zhihu.com/p/629623125)


## 感谢

项目取得的成果，需要感谢技术社区，尤其以下项目。

- [FastChat](https://github.com/lm-sys/FastChat) 提供 chat 服务
- [vicuna-13b](https://huggingface.co/Tribbiani/vicuna-13b) 作为基础模型
- [langchain](https://github.com/hwchase17/langchain) 工具链
- [Auto-GPT](https://github.com/Significant-Gravitas/Auto-GPT) 通用的插件模版
- [Hugging Face](https://huggingface.co/) 大模型管理
- [Chroma](https://github.com/chroma-core/chroma) 向量存储
- [Milvus](https://milvus.io/) 分布式向量存储
- [ChatGLM](https://github.com/THUDM/ChatGLM-6B) 基础模型
- [llama-index](https://github.com/jerryjliu/llama_index) 基于现有知识库进行[In-Context Learning](https://arxiv.org/abs/2301.00234)来对其进行数据库相关知识的增强。

# 贡献

- 提交代码前请先执行 `black .`

这是一个用于数据库的复杂且创新的工具, 我们的项目也在紧急的开发当中, 会陆续发布一些新的feature。如在使用当中有任何具体问题, 优先在项目下提issue, 如有需要, 请联系如下微信，我会尽力提供帮助，同时也非常欢迎大家参与到项目建设中。



# 路线图

<p align="left">
  <img src="./assets/roadmap.jpg" width="800px" />
</p>

## 联系我们
微信群已超扫码加群上限, 进群请添加如下微信帮拉进群。

--------------
|xy643854343|mingtian2635|chenB305|cfq1612784863|
|-----------|----------|-----------|---------------|
## Licence

The MIT License (MIT)

