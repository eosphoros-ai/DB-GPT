# <img src="./assets/LOGO_SMALL.png" alt="Logo" style="vertical-align: middle; height: 24px;" /> DB-GPT: AI Native Data App Development framework with AWEL and Agents

<p align="left">
  <img src="./assets/Twitter_LOGO.png" width="100%" />
</p>

<div align="center">
  <p>
    <a href="https://github.com/eosphoros-ai/DB-GPT">
        <img alt="stars" src="https://img.shields.io/github/stars/eosphoros-ai/db-gpt?style=social" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT">
        <img alt="forks" src="https://img.shields.io/github/forks/eosphoros-ai/db-gpt?style=social" />
    </a>
    <a href="http://dbgpt.cn/">
        <img alt="Official Website" src="https://img.shields.io/badge/Official%20website-DB--GPT-blue?style=flat&labelColor=3366CC" />
    </a>
    <a href="https://opensource.org/licenses/MIT">
      <img alt="License: MIT" src="https://img.shields.io/github/license/eosphoros-ai/db-gpt?style=flat&labelColor=009966&color=009933" />
    </a>
     <a href="https://github.com/eosphoros-ai/DB-GPT/releases">
      <img alt="Release Notes" src="https://img.shields.io/github/v/release/eosphoros-ai/db-gpt?style=flat&labelColor=FF9933&color=FF6633" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT/issues">
      <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/eosphoros-ai/db-gpt?style=flat&labelColor=666666&color=333333" />
    </a>
    <a href="https://x.com/DBGPT_AI">
      <img alt="X (formerly Twitter) Follow" src="https://img.shields.io/twitter/follow/DBGPT_AI" />
    </a>
    <a href="https://medium.com/@dbgpt0506">
      <img alt="Medium Follow" src="https://badgen.net/badge/Medium/DB-GPT/333333?icon=medium&labelColor=666666" />
    </a>
    <a href="https://space.bilibili.com/3537113070963392">
      <img alt="Bilibili Space" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.bilibili.com%2Fx%2Frelation%2Fstat%3Fvmid%3D3537113070963392&query=data.follower&style=flat&logo=bilibili&logoColor=white&label=Bilibili%20Fans&labelColor=F37697&color=6495ED" />
    </a>
    <a href="https://join.slack.com/t/slack-inu2564/shared_invite/zt-29rcnyw2b-N~ubOD9kFc7b7MDOAM1otA">
      <img alt="Slack" src="https://img.shields.io/badge/Slack-Join%20us-5d6b98?style=flat&logo=slack&labelColor=7d89b0" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[![English](https://img.shields.io/badge/English-d9d9d9?style=flat-square)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-d9d9d9?style=flat-square)](README.zh.md)
[![日本語](https://img.shields.io/badge/日本語-d9d9d9?style=flat-square)](README.ja.md) 

[**Documents**](http://docs.dbgpt.cn/docs/overview/) | [**Contact Us**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**Community**](https://github.com/eosphoros-ai/community) | [**Paper**](https://arxiv.org/pdf/2312.17449.pdf)

</div>

## What is DB-GPT?

🤖 **DB-GPT is an open source AI native data app development framework with AWEL(Agentic Workflow Expression Language) and agents**. 

The purpose is to build infrastructure in the field of large models, through the development of multiple technical capabilities such as multi-model management (SMMF), Text2SQL effect optimization, RAG framework and optimization, Multi-Agents framework collaboration, AWEL (agent workflow orchestration), etc. Which makes large model applications with data simpler and more convenient.

🚀 **In the Data 3.0 era, based on models and databases, enterprises and developers can build their own bespoke applications with less code.**

### Introduction 
The architecture of DB-GPT is shown in the following figure:

<p align="center">
  <img src="./assets/dbgpt.png" width="800" />
</p>

The core capabilities include the following parts:

- **RAG (Retrieval Augmented Generation)**: RAG is currently the most practically implemented and urgently needed domain. DB-GPT has already implemented a framework based on RAG, allowing users to build knowledge-based applications using the RAG capabilities of DB-GPT.

- **GBI (Generative Business Intelligence)**: Generative BI is one of the core capabilities of the DB-GPT project, providing the foundational data intelligence technology to build enterprise report analysis and business insights.

- **Fine-tuning Framework**: Model fine-tuning is an indispensable capability for any enterprise to implement in vertical and niche domains. DB-GPT provides a complete fine-tuning framework that integrates seamlessly with the DB-GPT project. In recent fine-tuning efforts, an accuracy rate based on the Spider dataset has been achieved at 82.5%.

- **Data-Driven Multi-Agents Framework**: DB-GPT offers a data-driven self-evolving multi-agents framework, aiming to continuously make decisions and execute based on data.

- **Data Factory**: The Data Factory is mainly about cleaning and processing trustworthy knowledge and data in the era of large models.

- **Data Sources**: Integrating various data sources to seamlessly connect production business data to the core capabilities of DB-GPT.

#### SubModule
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) Text-to-SQL workflow with high performance by applying Supervised Fine-Tuning (SFT) on Large Language Models (LLMs).

- [dbgpts](https://github.com/eosphoros-ai/dbgpts)  dbgpts is the official repository which contains some data apps、AWEL operators、AWEL workflow templates and agents which build upon DB-GPT.

#### Text2SQL Finetune

  |     LLM     |  Supported  | 
  |:-----------:|:-----------:|
  |    LLaMA    |      ✅     |
  |   LLaMA-2   |      ✅     | 
  |    BLOOM    |      ✅     | 
  |   BLOOMZ    |      ✅     | 
  |   Falcon    |      ✅     | 
  |  Baichuan   |      ✅     | 
  |  Baichuan2  |      ✅     | 
  |  InternLM   |      ✅     |
  |    Qwen     |      ✅     | 
  |   XVERSE    |      ✅     | 
  |  ChatGLM2   |      ✅     |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        


[More Information about Text2SQL finetune](https://github.com/eosphoros-ai/DB-GPT-Hub)

- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT Plugins that can run Auto-GPT plugin directly
- [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) Visualization protocol

### AI-Native Data App 
---
- 🔥🔥🔥 [Released V0.7.0 | A set of significant upgrades](http://docs.dbgpt.cn/blog/db-gpt-v070-release)
  - [Support MCP Protocol](https://github.com/eosphoros-ai/DB-GPT/pull/2497)
  - [Support DeepSeek R1](https://github.com/deepseek-ai/DeepSeek-R1)
  - [Support QwQ-32B](https://huggingface.co/Qwen/QwQ-32B)
  - [Refactor the basic modules]()
    - [dbgpt-app](./packages/dbgpt-app)
    - [dbgpt-core](./packages/dbgpt-core)
    - [dbgpt-serve](./packages/dbgpt-serve)
    - [dbgpt-client](./packages/dbgpt-client)
    - [dbgpt-accelerator](./packages/dbgpt-accelerator)
    - [dbgpt-ext](./packages/dbgpt-ext)
---

![app_chat_v0 6](https://github.com/user-attachments/assets/a2f0a875-df8c-4f0d-89a3-eed321c02113)

![app_manage_chat_data_v0 6](https://github.com/user-attachments/assets/c8cc85bb-e3c2-4fab-8fb9-7b4b469d0611)

![chat_dashboard_display_v0 6](https://github.com/user-attachments/assets/b15d6ebe-54c4-4527-a16d-02fbbaf20dc9)

![agent_prompt_awel_v0 6](https://github.com/user-attachments/assets/40761507-a1e1-49d4-b49a-3dd9a5ea41cc)


## Installation / Quick Start 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**Usage Tutorial**](http://docs.dbgpt.cn/docs/overview)
- [**Install**](http://docs.dbgpt.cn/docs/installation)
  - [Docker](http://docs.dbgpt.cn/docs/installation/docker)
  - [Source Code](http://docs.dbgpt.cn/docs/installation/sourcecode)
- [**Quickstart**](http://docs.dbgpt.cn/docs/quickstart)
- [**Application**](http://docs.dbgpt.cn/docs/operation_manual)
  - [Development Guide](http://docs.dbgpt.cn/docs/cookbook/app/data_analysis_app_develop) 
  - [App Usage](http://docs.dbgpt.cn/docs/application/app_usage)
  - [AWEL Flow Usage](http://docs.dbgpt.cn/docs/application/awel_flow_usage)
- [**Debugging**](http://docs.dbgpt.cn/docs/operation_manual/advanced_tutorial/debugging)
- [**Advanced Usage**](http://docs.dbgpt.cn/docs/application/advanced_tutorial/cli)
  - [SMMF](http://docs.dbgpt.cn/docs/application/advanced_tutorial/smmf)
  - [Finetune](http://docs.dbgpt.cn/docs/application/fine_tuning_manual/dbgpt_hub)
  - [AWEL](http://docs.dbgpt.cn/docs/awel/tutorial)


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

  - News
    <table>
      <thead>
        <tr>
          <th>Provider</th>
          <th>Supported</th>
          <th>Models</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td align="center" valign="middle">DeepSeek</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1-0528">DeepSeek-R1-0528</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-V3-0324">DeepSeek-V3-0324</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1">DeepSeek-R1</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-V3">DeepSeek-V3</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-70B">DeepSeek-R1-Distill-Llama-70B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B">DeepSeek-R1-Distill-Qwen-32B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/deepseek-ai/DeepSeek-Coder-V2-Instruct">DeepSeek-Coder-V2-Instruct</a><br/>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Qwen</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen3-235B-A22B">Qwen3-235B-A22B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen3-30B-A3B">Qwen3-30B-A3B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen3-32B">Qwen3-32B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/QwQ-32B">QwQ-32B</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct">Qwen2.5-Coder-32B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct">Qwen2.5-Coder-14B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-72B-Instruct">Qwen2.5-72B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/Qwen/Qwen2.5-32B-Instruct">Qwen2.5-32B-Instruct</a><br/>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">GLM</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/THUDM/GLM-Z1-32B-0414">GLM-Z1-32B-0414</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/THUDM/GLM-4-32B-0414">GLM-4-32B-0414</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/THUDM/glm-4-9b-chat">Glm-4-9b-chat</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Llama</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3.1-405B-Instruct">Meta-Llama-3.1-405B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3.1-70B-Instruct">Meta-Llama-3.1-70B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3.1-8B-Instruct">Meta-Llama-3.1-8B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct">Meta-Llama-3-70B-Instruct</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct">Meta-Llama-3-8B-Instruct</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Gemma</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-2-27b-it">gemma-2-27b-it</a><br>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-2-9b-it">gemma-2-9b-it</a><br>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-7b-it">gemma-7b-it</a><br>
            🔥🔥🔥  <a href="https://huggingface.co/google/gemma-2b-it">gemma-2b-it</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Yi</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-1.5-34B-Chat">Yi-1.5-34B-Chat</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-1.5-9B-Chat">Yi-1.5-9B-Chat</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-1.5-6B-Chat">Yi-1.5-6B-Chat</a><br/>
            🔥🔥🔥  <a href="https://huggingface.co/01-ai/Yi-34B-Chat">Yi-34B-Chat</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Starling</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/Nexusflow/Starling-LM-7B-beta">Starling-LM-7B-beta</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">SOLAR</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/upstage/SOLAR-10.7B-Instruct-v1.0">SOLAR-10.7B</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Mixtral</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/mistralai/Mixtral-8x7B-Instruct-v0.1">Mixtral-8x7B</a>
          </td>
        </tr>
        <tr>
          <td align="center" valign="middle">Phi</td>
          <td align="center" valign="middle">✅</td>
          <td>
            🔥🔥🔥  <a href="https://huggingface.co/collections/microsoft/phi-3-6626e15e9585a200d2d761e3">Phi-3</a>
          </td>
        </tr>
      </tbody>
    </table>

  - [More Supported LLMs](http://docs.dbgpt.site/docs/modules/smmf)

- **Privacy and Security**
  
  We ensure the privacy and security of data through the implementation of various technologies, including privatized large models and proxy desensitization.

- Support Datasources
  - [Datasources](http://docs.dbgpt.cn/docs/modules/connections)

## Image
🌐 [AutoDL Image](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)



## Contribution

- To check detailed guidelines for new contributions, please refer [how to contribute](https://github.com/eosphoros-ai/DB-GPT/blob/main/CONTRIBUTING.md)

### Contributors Wall
<a href="https://github.com/eosphoros-ai/DB-GPT/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=eosphoros-ai/DB-GPT&max=200" />
</a>


## Licence
The MIT License (MIT)

## DISCKAIMER
- [disckaimer](./DISCKAIMER.md)

## Citation
If you want to understand the overall architecture of DB-GPT, please cite <a href="https://arxiv.org/abs/2312.17449" target="_blank">Paper</a> and <a href="https://arxiv.org/abs/2404.10209" target="_blank">Paper</a>

If you want to learn about using DB-GPT for Agent development, please cite the <a href="https://arxiv.org/abs/2412.13520" target="_blank">Paper</a>
```bibtex
@article{xue2023dbgpt,
      title={DB-GPT: Empowering Database Interactions with Private Large Language Models}, 
      author={Siqiao Xue and Caigao Jiang and Wenhui Shi and Fangyin Cheng and Keting Chen and Hongjun Yang and Zhiping Zhang and Jianshan He and Hongyang Zhang and Ganglin Wei and Wang Zhao and Fan Zhou and Danrui Qi and Hong Yi and Shaodong Liu and Faqiang Chen},
      year={2023},
      journal={arXiv preprint arXiv:2312.17449},
      url={https://arxiv.org/abs/2312.17449}
}
@misc{huang2024romasrolebasedmultiagentdatabase,
      title={ROMAS: A Role-Based Multi-Agent System for Database monitoring and Planning}, 
      author={Yi Huang and Fangyin Cheng and Fan Zhou and Jiahui Li and Jian Gong and Hongjun Yang and Zhidong Fan and Caigao Jiang and Siqiao Xue and Faqiang Chen},
      year={2024},
      eprint={2412.13520},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2412.13520}, 
}
@inproceedings{xue2024demonstration,
      title={Demonstration of DB-GPT: Next Generation Data Interaction System Empowered by Large Language Models}, 
      author={Siqiao Xue and Danrui Qi and Caigao Jiang and Wenhui Shi and Fangyin Cheng and Keting Chen and Hongjun Yang and Zhiping Zhang and Jianshan He and Hongyang Zhang and Ganglin Wei and Wang Zhao and Fan Zhou and Hong Yi and Shaodong Liu and Hongjun Yang and Faqiang Chen},
      year={2024},
      booktitle = "Proceedings of the VLDB Endowment",
      url={https://arxiv.org/abs/2404.10209}
}
```


## Contact Information
Thanks to everyone who has contributed to DB-GPT! Your ideas, code, comments, and even sharing them at events and on social platforms can make DB-GPT better.
We are working on building a community, if you have any ideas for building the community, feel free to contact us.  

- [Github Issues](https://github.com/eosphoros-ai/DB-GPT/issues) ⭐️：For questions about using GB-DPT, see the CONTRIBUTING.  
- [Github Discussions](https://github.com/orgs/eosphoros-ai/discussions) ⭐️：Share your experience or unique apps.  
- [Twitter](https://x.com/DBGPT_AI) ⭐️：Please feel free to talk to us.  


[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
