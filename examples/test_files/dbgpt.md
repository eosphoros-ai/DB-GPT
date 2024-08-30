# DB-GPT: 用私有化LLM技术定义数据库下一代交互方式
## DB-GPT 是什么？
🤖️ **DB-GPT是一个开源的AI原生数据应用开发框架(AI Native Data App Development framework with AWEL(Agentic Workflow Expression Language) and Agents)。**
目的是构建大模型领域的基础设施，通过开发多模型管理(SMMF)、Text2SQL效果优化、RAG框架以及优化、Multi-Agents框架协作、AWEL(智能体工作流编排)等多种技术能力，让围绕数据库构建大模型应用更简单，更方便。 
🚀 **数据3.0 时代，基于模型、数据库，企业/开发者可以用更少的代码搭建自己的专属应用。**
## 效果演示
### AI原生数据智能应用

---

- 🔥🔥🔥 [V0.5.0发布——通过工作流与智能体开发原生数据应用](https://www.yuque.com/eosphoros/dbgpt-docs/owcrh9423f9rqkg2)

---

### Data Agents
![](https://github.com/eosphoros-ai/DB-GPT/assets/17919400/37d116fc-d9dd-4efa-b4df-9ab02b22541c#id=KpPbI&originHeight=1880&originWidth=3010&originalType=binary&ratio=1&rotation=0&showTitle=false&status=done&style=none)
![](https://github.com/eosphoros-ai/DB-GPT/assets/17919400/a7bf6d65-92d1-4f0e-aaf0-259ccdde22fd#id=EHUr0&originHeight=1872&originWidth=3396&originalType=binary&ratio=1&rotation=0&showTitle=false&status=done&style=none)
![](https://github.com/eosphoros-ai/DB-GPT/assets/17919400/1849a79a-f7fd-40cf-bc9c-b117a041dd6a#id=gveW4&originHeight=1868&originWidth=2996&originalType=binary&ratio=1&rotation=0&showTitle=false&status=done&style=none)
## 目录

- [架构方案](#架构方案)
- [安装](#安装)
- [特性简介](#特性一览)
- [贡献](#贡献)
- [路线图](#路线图)
- [联系我们](#联系我们)
## 架构方案
![image.png](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1724764757479-314c8ed2-24e6-4cc2-8a29-e84e626d6755.png#clientId=u47bade0c-6d5b-4&from=paste&height=721&id=u6344fee6&originHeight=1442&originWidth=1590&originalType=binary&ratio=2&rotation=0&showTitle=false&size=766959&status=done&style=none&taskId=u0f69fc62-9392-468b-a990-84de8e3a3eb&title=&width=795)
核心能力主要有以下几个部分:

- **RAG(Retrieval Augmented Generation)**，RAG是当下落地实践最多，也是最迫切的领域，DB-GPT目前已经实现了一套基于RAG的框架，用户可以基于DB-GPT的RAG能力构建知识类应用。 
- **GBI**：生成式BI是DB-GPT项目的核心能力之一，为构建企业报表分析、业务洞察提供基础的数智化技术保障。 
- **微调框架**:  模型微调是任何一个企业在垂直、细分领域落地不可或缺的能力，DB-GPT提供了完整的微调框架，实现与DB-GPT项目的无缝打通，在最近的微调中，基于spider的准确率已经做到了82.5%
- **数据驱动的Multi-Agents框架**:  DB-GPT提供了数据驱动的自进化Multi-Agents框架，目标是可以持续基于数据做决策与执行。 
- **数据工厂**: 数据工厂主要是在大模型时代，做可信知识、数据的清洗加工。 
- **数据源**: 对接各类数据源，实现生产业务数据无缝对接到DB-GPT核心能力。
### 智能体编排语言(AWEL)
AWEL（Agentic Workflow Expression Language）是一套专为大模型应用开发设计的智能体工作流表达语言，它提供了强大的功能和灵活性。通过 AWEL API 您可以专注于大模型应用业务逻辑的开发，而不需要关注繁琐的模型和环境细节，AWEL 采用分层 API 的设计， AWEL 的分层 API 设计架构如下图所示：

![image.png](https://cdn.nlark.com/yuque/0/2023/png/23108892/1700743735979-fcae1255-5b21-4071-a805-84d9f98247ef.png#averageHue=%23efefef&clientId=u62c750d6-91b4-4&from=paste&height=588&id=ua7e2a75b&originHeight=819&originWidth=586&originalType=binary&ratio=2&rotation=0&showTitle=false&size=101075&status=done&style=shadow&taskId=u753583cb-7d4f-4267-962d-a892e5150d2&title=&width=421)

AWEL在设计上分为三个层次，依次为算子层、AgentFrame层以及DSL层，以下对三个层次做简要介绍。 

- 算子层

算子层是指LLM应用开发过程中一个个最基本的操作原子，比如在一个RAG应用开发时。 检索、向量化、模型交互、Prompt处理等都是一个个基础算子。 在后续的发展中，框架会进一步对算子进行抽象与标准化设计。 可以根据标准API快速实现一组算子。

- AgentFrame层

AgentFrame层将算子做进一步封装，可以基于算子做链式计算。 这一层链式计算也支持分布式，支持如filter、join、map、reduce等一套链式计算操作。 后续也将支持更多的计算逻辑。

- DSL层

DSL层提供一套标准的结构化表示语言，可以通过写DSL语句完成AgentFrame与算子的操作，让围绕数据编写大模型应用更具确定性，避免通过自然语言编写的不确定性，使得围绕数据与大模型的应用编程变为确定性应用编程。
### RAG架构
![](https://github.com/eosphoros-ai/DB-GPT/raw/main/assets/RAG-IN-ACTION.jpg#from=url&id=JsJTm&originHeight=1300&originWidth=2272&originalType=binary&ratio=2&rotation=0&showTitle=false&status=done&style=none&title=)
### Agent架构
DB-GPT Agent是一个多Agent框架，目的是提供生产级Agent构建的基础框架能力。我们认为，生产级代理应用程序需要基于数据驱动的决策，并且可以在可控制的工作流中进行编排。
在我们的设计中，提供了一套以Agent为核心，融合多模型管理、RAGs、API调用、可视化、AWEL智能体编排、Text2SQL、意图识别等一系列技术的生产级数据应用开发框架。 
![image.png](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1724765648901-d048c6fc-8b08-4623-bc2d-66db8edb893f.png#clientId=u47bade0c-6d5b-4&from=paste&height=376&id=u580c84f4&originHeight=558&originWidth=1076&originalType=binary&ratio=2&rotation=0&showTitle=false&size=862016&status=done&style=none&taskId=ue3fa55ab-171a-4aeb-a7ec-8bcf8e13474&title=&width=725)
如同所示:  在DB-GPT中，Agent是一等公民，其他RAGs、Tools、数据源等都是Agent依赖的资源，包括模型也是一种资源。 
Agent的核心模块主要有Memory、Profile、Planing、Action等模块。 
围绕Agent的核心模块，往上构建多Agent之间的协作能力，协作主要有三种形式。 

1. 单一Agent: 单个Agent有具体任务与目标，不涉及多模型协作。 
2. Auto-Plan: Agent自己制定计划，在多Agent协作时负责路径规划、分工协作等。
3. AWEL: 编排，通过程序编排来实现多智能体的协作。
### 多模型架构
在AIGC应用探索与生产落地中，难以避免直接与模型服务对接，但是目前大模型的推理部署还没有一个事实标准，不断有新的模型发布，也不断有新的训练方法被提出，我们需要花大量的时间来适配多变的底层模型环境，而这在一定程度上制约了AIGC应用的探索和落地。 
![](https://intranetproxy.alipay.com/skylark/lark/0/2024/png/26456775/1724765743005-eb151d72-79a2-4a91-9d85-f46b68bfe031.png#clientId=u47bade0c-6d5b-4&from=paste&id=u26061337&originHeight=1087&originWidth=1439&originalType=url&ratio=2&rotation=0&showTitle=false&status=done&style=none&taskId=u181cfde4-f672-414c-a030-07d40dee916&title=)
SMMF由模型推理层、模型部署层两部分组成。模型推理层对应模型推理框架vLLM、TGI和TensorRT等。模型部署层向下对接推理层，向上提供模型服务能力。 模型部署框架在推理框架之上，提供了多模型实例、多推理框架、多云、自动扩缩容与可观测性等能力。
### 子模块

- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) 通过微调来持续提升Text2SQL效果 
- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT 插件仓库, 兼容Auto-GPT
- [GPT-Vis](https://github.com/eosphoros-ai/DB-GPT-Web) 可视化协议 
- [dbgpts](https://github.com/eosphoros-ai/dbgpts)  dbgpts 是官方提供的数据应用仓库, 包含数据智能应用, 智能体编排流程模版, 通用算子等构建在DB-GPT之上的资源。
## 安装
[**教程**](https://www.yuque.com/eosphoros/dbgpt-docs/bex30nsv60ru0fmx)

- [**快速开始**](https://www.yuque.com/eosphoros/dbgpt-docs/ew0kf1plm0bru2ga)
   - [源码安装](https://www.yuque.com/eosphoros/dbgpt-docs/urh3fcx8tu0s9xmb)
   - [Docker安装](https://www.yuque.com/eosphoros/dbgpt-docs/glf87qg4xxcyrp89)
   - [Docker Compose安装](https://www.yuque.com/eosphoros/dbgpt-docs/wwdu11e0v5nkfzin)
- [**使用手册**](https://www.yuque.com/eosphoros/dbgpt-docs/tkspdd0tcy2vlnu4)
   - [知识库](https://www.yuque.com/eosphoros/dbgpt-docs/ycyz3d9b62fccqxh)
   - [数据对话](https://www.yuque.com/eosphoros/dbgpt-docs/gd9hbhi1dextqgbz)
   - [Excel对话](https://www.yuque.com/eosphoros/dbgpt-docs/prugoype0xd2g4bb)
   - [数据库对话](https://www.yuque.com/eosphoros/dbgpt-docs/wswpv3zcm2c9snmg)
   - [报表分析](https://www.yuque.com/eosphoros/dbgpt-docs/vsv49p33eg4p5xc1)
   - [Agents](https://www.yuque.com/eosphoros/dbgpt-docs/pom41m7oqtdd57hm)
- [**进阶教程**](https://www.yuque.com/eosphoros/dbgpt-docs/dxalqb8wsv2xkm5f)
   - [智能体工作流使用](https://www.yuque.com/eosphoros/dbgpt-docs/hcomfb3yrleg7gmq)
   - [智能应用使用](https://www.yuque.com/eosphoros/dbgpt-docs/aiagvxeb86iarq6r)
   - [多模型管理](https://www.yuque.com/eosphoros/dbgpt-docs/huzgcf2abzvqy8uv)
   - [命令行使用](https://www.yuque.com/eosphoros/dbgpt-docs/gd4kgumgd004aly8)
- [**模型服务部署**](https://www.yuque.com/eosphoros/dbgpt-docs/vubxiv9cqed5mc6o)
   - [单机部署](https://www.yuque.com/eosphoros/dbgpt-docs/kwg1ed88lu5fgawb)
   - [集群部署](https://www.yuque.com/eosphoros/dbgpt-docs/gmbp9619ytyn2v1s)
   - [vLLM](https://www.yuque.com/eosphoros/dbgpt-docs/bhy9igdvanx1uluf)
- [**如何Debug**](https://www.yuque.com/eosphoros/dbgpt-docs/eyg0ocbc2ce3q95r)
- [**AWEL**](https://www.yuque.com/eosphoros/dbgpt-docs/zozbzslbfk0m0op5)
- [**FAQ**](https://www.yuque.com/eosphoros/dbgpt-docs/gomtc46qonmyt44l)
## 特性一览

- **私域问答&数据处理&RAG**支持内置、多文件格式上传、插件自抓取等方式自定义构建知识库，对海量结构化，非结构化数据做统一向量存储与检索
- **多数据源&GBI**支持自然语言与Excel、数据库、数仓等多种数据源交互，并支持分析报告。
- **自动化微调**围绕大语言模型、Text2SQL数据集、LoRA/QLoRA/Pturning等微调方法构建的自动化微调轻量框架, 让TextSQL微调像流水线一样方便。详见: [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub)
- **数据驱动的Agents插件**支持自定义插件执行任务，原生支持Auto-GPT插件模型，Agents协议采用Agent Protocol标准
- **多模型支持与管理**海量模型支持，包括开源、API代理等几十种大语言模型。如LLaMA/LLaMA2、Baichuan、ChatGLM、文心、通义、智谱等。当前已支持如下模型: 
   - 新增支持模型
      - 🔥🔥🔥  [Meta-Llama-3.1-405B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-405B-Instruct)
      - 🔥🔥🔥  [Meta-Llama-3.1-70B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-70B-Instruct)
      - 🔥🔥🔥  [Meta-Llama-3.1-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct)
      - 🔥🔥🔥  [gemma-2-27b-it](https://huggingface.co/google/gemma-2-27b-it)
      - 🔥🔥🔥  [gemma-2-9b-it](https://huggingface.co/google/gemma-2-9b-it)
      - 🔥🔥🔥  [DeepSeek-Coder-V2-Instruct](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct)
      - 🔥🔥🔥  [DeepSeek-Coder-V2-Lite-Instruct](https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct)
      - 🔥🔥🔥  [Qwen2-57B-A14B-Instruct](https://huggingface.co/Qwen/Qwen2-57B-A14B-Instruct)
      - 🔥🔥🔥  [Qwen2-57B-A14B-Instruct](https://huggingface.co/Qwen/Qwen2-57B-A14B-Instruct)
      - 🔥🔥🔥  [Qwen2-72B-Instruct](https://huggingface.co/Qwen/Qwen2-72B-Instruct)
      - 🔥🔥🔥  [Qwen2-7B-Instruct](https://huggingface.co/Qwen/Qwen2-7B-Instruct)
      - 🔥🔥🔥  [Qwen2-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2-1.5B-Instruct)
      - 🔥🔥🔥  [Qwen2-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2-0.5B-Instruct)
      - 🔥🔥🔥  [glm-4-9b-chat](https://huggingface.co/THUDM/glm-4-9b-chat)
      - 🔥🔥🔥  [Phi-3](https://huggingface.co/collections/microsoft/phi-3-6626e15e9585a200d2d761e3)
      - 🔥🔥🔥  [Yi-1.5-34B-Chat](https://huggingface.co/01-ai/Yi-1.5-34B-Chat)
      - 🔥🔥🔥  [Yi-1.5-9B-Chat](https://huggingface.co/01-ai/Yi-1.5-9B-Chat)
      - 🔥🔥🔥  [Yi-1.5-6B-Chat](https://huggingface.co/01-ai/Yi-1.5-6B-Chat)
      - 🔥🔥🔥  [Qwen1.5-110B-Chat](https://huggingface.co/Qwen/Qwen1.5-110B-Chat)
      - 🔥🔥🔥  [Qwen1.5-MoE-A2.7B-Chat](https://huggingface.co/Qwen/Qwen1.5-MoE-A2.7B-Chat)
      - 🔥🔥🔥  [Meta-Llama-3-70B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct)
      - 🔥🔥🔥  [Meta-Llama-3-8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct)
      - 🔥🔥🔥  [CodeQwen1.5-7B-Chat](https://huggingface.co/Qwen/CodeQwen1.5-7B-Chat)
      - 🔥🔥🔥  [Qwen1.5-32B-Chat](https://huggingface.co/Qwen/Qwen1.5-32B-Chat)
      - 🔥🔥🔥  [Starling-LM-7B-beta](https://huggingface.co/Nexusflow/Starling-LM-7B-beta)
      - 🔥🔥🔥  [gemma-7b-it](https://huggingface.co/google/gemma-7b-it)
      - 🔥🔥🔥  [gemma-2b-it](https://huggingface.co/google/gemma-2b-it)
      - 🔥🔥🔥  [SOLAR-10.7B](https://huggingface.co/upstage/SOLAR-10.7B-Instruct-v1.0)
      - 🔥🔥🔥  [Mixtral-8x7B](https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1)
      - 🔥🔥🔥  [Qwen-72B-Chat](https://huggingface.co/Qwen/Qwen-72B-Chat)
      - 🔥🔥🔥  [Yi-34B-Chat](https://huggingface.co/01-ai/Yi-34B-Chat)
   - [更多开源模型](https://www.yuque.com/eosphoros/dbgpt-docs/iqaaqwriwhp6zslc#qQktR)
   - 支持在线代理模型
- [x] [DeepSeek.deepseek-chat](https://platform.deepseek.com/api-docs/)
- [x] [Ollama.API](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [x] [月之暗面.Moonshot](https://platform.moonshot.cn/docs/)
- [x] [零一万物.Yi](https://platform.lingyiwanwu.com/docs)
- [x] [OpenAI·ChatGPT](https://api.openai.com/)
- [x] [百川·Baichuan](https://platform.baichuan-ai.com/)
- [x] [阿里·通义](https://www.aliyun.com/product/dashscope)
- [x] [百度·文心](https://cloud.baidu.com/product/wenxinworkshop?track=dingbutonglan)
- [x] [智谱·ChatGLM](http://open.bigmodel.cn/)
- [x] [讯飞·星火](https://xinghuo.xfyun.cn/)
- [x] [Google·Bard](https://bard.google.com/)
- [x] [Google·Gemini](https://makersuite.google.com/app/apikey)
- **隐私安全**通过私有化大模型、代理脱敏等多种技术保障数据的隐私安全。
- [支持数据源](https://www.yuque.com/eosphoros/dbgpt-docs/rc4r27ybmdwg9472)
## Image
🌐 [AutoDL镜像](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)
🌐 [小程序云部署](https://www.yuque.com/eosphoros/dbgpt-docs/ek12ly8k661tbyn8)
### 多语言切换
在.env 配置文件当中，修改LANGUAGE参数来切换使用不同的语言，默认是英文(中文zh, 英文en, 其他语言待补充)
## 使用说明
### 多模型使用
### 数据Agents使用

- [数据Agents](https://www.yuque.com/eosphoros/dbgpt-docs/gwz4rayfuwz78fbq)
## 贡献
## 更加详细的贡献指南请参考[如何贡献](https://github.com/eosphoros-ai/DB-GPT/blob/main/CONTRIBUTING.md)。
这是一个用于数据库的复杂且创新的工具, 我们的项目也在紧急的开发当中, 会陆续发布一些新的feature。如在使用当中有任何具体问题, 优先在项目下提issue, 如有需要, 请联系如下微信，我会尽力提供帮助，同时也非常欢迎大家参与到项目建设中。
## Licence
The MIT License (MIT)
## 引用
如果您发现`DB-GPT`对您的研究或开发有用，请引用以下[论文](https://arxiv.org/abs/2312.17449)：
```
@article{xue2023dbgpt,
      title={DB-GPT: Empowering Database Interactions with Private Large Language Models}, 
      author={Siqiao Xue and Caigao Jiang and Wenhui Shi and Fangyin Cheng and Keting Chen and Hongjun Yang and Zhiping Zhang and Jianshan He and Hongyang Zhang and Ganglin Wei and Wang Zhao and Fan Zhou and Danrui Qi and Hong Yi and Shaodong Liu and Faqiang Chen},
      year={2023},
      journal={arXiv preprint arXiv:2312.17449},
      url={https://arxiv.org/abs/2312.17449}
}
```

