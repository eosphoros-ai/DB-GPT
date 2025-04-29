# DB-GPT: データベースとの対話を革新するプライベートLLM技術

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
     <a href="https://github.com/eosphoros-ai/DB-GPT/releases">
      <img alt="Release Notes" src="https://img.shields.io/github/release/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT/issues">
      <img alt="Open Issues" src="https://img.shields.io/github/issues-raw/eosphoros-ai/DB-GPT" />
    </a>
    <a href="https://discord.gg/7uQnPuveTY">
      <img alt="Discord" src="https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat" />
    </a>
    <a href="https://join.slack.com/t/slack-inu2564/shared_invite/zt-29rcnyw2b-N~ubOD9kFc7b7MDOAM1otA">
      <img alt="Slack" src="https://badgen.net/badge/Slack/Join%20DB-GPT/0abd59?icon=slack" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="Open in GitHub Codespaces" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>

[**英語**](README.md) | [**中国語**](README.zh.md) | [**Discord**](https://discord.gg/7uQnPuveTY) | [**ドキュメント**](https://docs.dbgpt.site) | [**微信**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**コミュニティ**](https://github.com/eosphoros-ai/community) | [**論文**](https://arxiv.org/pdf/2312.17449.pdf)

</div>

## DB-GPTとは何か？

🤖 **DB-GPTは、AWEL（エージェントワークフロー式言語）とエージェントを備えたオープンソースのAIネイティブデータアプリ開発フレームワークです。**

大規模モデルの分野でのインフラを構築することを目的としており、SMMF（マルチモデル管理）、Text2SQL効果の最適化、RAGフレームワークと最適化、マルチエージェントフレームワークの協力、AWEL（エージェントワークフローのオーケストレーション）など、複数の技術機能の開発を通じて、データを使用した大規模モデルアプリケーションをよりシンプルで便利にします。

🚀 **データ3.0時代には、モデルとデータベースを基盤として、企業や開発者がより少ないコードで独自のアプリケーションを構築できます。**

### AIネイティブデータアプリ
- 🔥🔥🔥 [V0.7.0 リリース | 重要なアップグレードのセット](http://docs.dbgpt.cn/blog/db-gpt-v070-release)
  - [サポート MCP Protocol](https://github.com/eosphoros-ai/DB-GPT/pull/2497)
  - [サポート DeepSeek R1](https://github.com/deepseek-ai/DeepSeek-R1)
  - [サポート QwQ-32B](https://huggingface.co/Qwen/QwQ-32B)
  - [基本モジュールをリファクタリングする]()
    - [dbgpt-app](./packages/dbgpt-app)
    - [dbgpt-core](./packages/dbgpt-core)
    - [dbgpt-serve](./packages/dbgpt-serve)
    - [dbgpt-client](./packages/dbgpt-client)
    - [dbgpt-accelerator](./packages/dbgpt-accelerator)
    - [dbgpt-ext](./packages/dbgpt-ext)

![Data-awels](https://github.com/eosphoros-ai/DB-GPT/assets/17919400/37d116fc-d9dd-4efa-b4df-9ab02b22541c)

![Data-Apps](https://github.com/eosphoros-ai/DB-GPT/assets/17919400/a7bf6d65-92d1-4f0e-aaf0-259ccdde22fd)

![dashboard-images](https://github.com/eosphoros-ai/DB-GPT/assets/17919400/1849a79a-f7fd-40cf-bc9c-b117a041dd6a)

## 目次
- [紹介](#紹介)
- [インストール](#インストール)
- [特徴](#特徴)
- [貢献](#貢献)
- [連絡先](#連絡先情報)

## 紹介
DB-GPTのアーキテクチャは以下の図に示されています：

<p align="center">
  <img src="./assets/dbgpt.png" width="800" />
</p>

コア機能には以下の部分が含まれます：

- **RAG（Retrieval Augmented Generation）**：現在、RAGは最も実用的に実装され、緊急に必要とされる領域です。DB-GPTは、RAGの機能を使用して知識ベースのアプリケーションを構築できるようにする、RAGに基づくフレームワークをすでに実装しています。

- **GBI（Generative Business Intelligence）**：Generative BIはDB-GPTプロジェクトのコア機能の1つであり、企業のレポート分析とビジネスインサイトを構築するための基本的なデータインテリジェンス技術を提供します。

- **ファインチューニングフレームワーク**：モデルのファインチューニングは、任意の企業が垂直およびニッチなドメインで実装するために不可欠な機能です。DB-GPTは、DB-GPTプロジェクトとシームレスに統合される完全なファインチューニングフレームワークを提供します。最近のファインチューニングの取り組みでは、Spiderデータセットに基づいて82.5%の実行精度を達成しています。

- **データ駆動型マルチエージェントフレームワーク**：DB-GPTは、データに基づいて継続的に意思決定を行い、実行するためのデータ駆動型自己進化型マルチエージェントフレームワークを提供します。

- **データファクトリー**：データファクトリーは、主に大規模モデルの時代における信頼できる知識とデータのクリーニングと処理に関するものです。

- **データソース**：DB-GPTのコア機能に生産ビジネスデータをシームレスに接続するために、さまざまなデータソースを統合します。

### サブモジュール
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) 大規模言語モデル（LLM）上での教師ありファインチューニング（SFT）を適用することにより、高性能なText-to-SQLワークフロー。

- [dbgpts](https://github.com/eosphoros-ai/dbgpts)  dbgptsは、DB-GPT上で構築されたいくつかのデータアプリ、AWELオペレータ、AWELワークフローテンプレート、およびエージェントを含む公式リポジトリです。

#### Text2SQLファインチューニング
- サポートされているLLM
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

-  SFT精度
2023年10月10日現在、このプロジェクトを使用して130億パラメータのオープンソースモデルをファインチューニングすることにより、SpiderデータセットでGPT-4を超える実行精度を達成しました！

[Text2SQLファインチューニングに関する詳細情報](https://github.com/eosphoros-ai/DB-GPT-Hub)

- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) Auto-GPTプラグインを直接実行できるDB-GPTプラグイン
- [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) 可視化プロトコル

## インストール
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**使用チュートリアル**](http://docs.dbgpt.site/docs/overview)
- [**インストール**](http://docs.dbgpt.site/docs/installation)
  - [Docker](https://docs.dbgpt.site/docs/installation/docker)
  - [ソースコード](https://docs.dbgpt.site/docs/installation/sourcecode)
- [**クイックスタート**](http://docs.dbgpt.site/docs/quickstart)
- [**アプリケーション**](http://docs.dbgpt.site/docs/operation_manual)
  - [アプリの使用](https://docs.dbgpt.site/docs/application/app_usage)
  - [AWELフローの使用](https://docs.dbgpt.site/docs/application/awel_flow_usage)
- [**デバッグ**](http://docs.dbgpt.site/docs/operation_manual/advanced_tutorial/debugging)
- [**高度な使用法**](https://docs.dbgpt.site/docs/application/advanced_tutorial/cli)
  - [SMMF](https://docs.dbgpt.site/docs/application/advanced_tutorial/smmf)
  - [ファインチューニング](https://docs.dbgpt.site/docs/application/fine_tuning_manual/dbgpt_hub)
  - [AWEL](http://docs.dbgpt.cn/docs/awel/tutorial)

## 特徴

現在、私たちはいくつかの主要な機能を紹介して、現在の能力を示しています：
- **プライベートドメインQ&A＆データ処理**

  DB-GPTプロジェクトは、知識ベースの構築を改善し、構造化および非構造化データの両方の効率的なストレージと検索を可能にする一連の機能を提供します。これらの機能には、複数のファイル形式のアップロードのサポート、カスタムデータ抽出プラグインの統合、および大量の情報を効果的に管理するための統一されたベクトルストレージと検索機能が含まれます。

- **マルチデータソース＆GBI（Generative Business Intelligence）**

  DB-GPTプロジェクトは、Excel、データベース、データウェアハウスなどのさまざまなデータソースとの自然言語のシームレスな対話を容易にします。これらのソースから情報を照会および取得するプロセスを簡素化し、直感的な会話を行い、洞察を得ることができます。さらに、DB-GPTは分析レポートの生成をサポートし、ユーザーに貴重なデータの要約と解釈を提供します。

- **マルチエージェント＆プラグイン**

  さまざまなタスクを実行するためのカスタムプラグインのサポートを提供し、Auto-GPTプラグインモデルをネイティブにサポートしています。エージェントプロトコルは、エージェントプロトコル標準に準拠しています。

- **自動ファインチューニングText2SQL**

  私たちはまた、大規模言語モデル（LLM）、Text2SQLデータセット、LoRA/QLoRA/Pturningなどのファインチューニング方法を中心に、自動ファインチューニングの軽量フレームワークを開発しました。このフレームワークは、Text-to-SQLファインチューニングをアセンブリラインのように簡単にします。[DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub)

- **SMMF（サービス指向マルチモデル管理フレームワーク）**

  私たちは、LLaMA/LLaMA2、Baichuan、ChatGLM、Wenxin、Tongyi、Zhipuなど、オープンソースおよびAPIエージェントからの数十の大規模言語モデル（LLM）を含む幅広いモデルをサポートしています。

  - ニュース
    - 🔥🔥🔥  [Qwen3-235B-A22B](https://huggingface.co/Qwen/Qwen3-235B-A22B)
    - 🔥🔥🔥  [Qwen3-30B-A3B](https://huggingface.co/Qwen/Qwen3-30B-A3B)
    - 🔥🔥🔥  [Qwen3-32B](https://huggingface.co/Qwen/Qwen3-32B)
    - 🔥🔥🔥  [GLM-Z1-32B-0414](https://huggingface.co/THUDM/GLM-Z1-32B-0414)
    - 🔥🔥🔥  [GLM-4-32B-0414](https://huggingface.co/THUDM/GLM-4-32B-0414)
    - 🔥🔥🔥  [QwQ-32B](https://huggingface.co/Qwen/QwQ-32B)
    - 🔥🔥🔥  [DeepSeek-R1](https://huggingface.co/deepseek-ai/DeepSeek-R1)
    - 🔥🔥🔥  [DeepSeek-V3](https://huggingface.co/deepseek-ai/DeepSeek-V3)
    - 🔥🔥🔥  [DeepSeek-R1-Distill-Llama-70B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-70B)
    - 🔥🔥🔥  [DeepSeek-R1-Distill-Qwen-32B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-32B)
    - 🔥🔥🔥  [DeepSeek-R1-Distill-Qwen-14B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-14B)
    - 🔥🔥🔥  [DeepSeek-R1-Distill-Llama-8B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Llama-8B)
    - 🔥🔥🔥  [DeepSeek-R1-Distill-Qwen-7B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B)
    - 🔥🔥🔥  [DeepSeek-R1-Distill-Qwen-1.5B](https://huggingface.co/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B)
    - 🔥🔥🔥  [Qwen2.5-Coder-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-Coder-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-72B-Instruct](https://huggingface.co/Qwen/Qwen2.5-72B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-32B-Instruct](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-14B-Instruct](https://huggingface.co/Qwen/Qwen2.5-14B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-Coder-7B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)
    - 🔥🔥🔥  [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct)
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
  - [サポートされているLLMの詳細](http://docs.dbgpt.site/docs/modules/smmf)

- **プライバシーとセキュリティ**

  私たちは、さまざまな技術を実装することにより、データのプライバシーとセキュリティを確保しています。これには、大規模モデルのプライベート化とプロキシの非識別化が含まれます。

- サポートされているデータソース
  - [データソース](http://docs.dbgpt.site/docs/modules/connections)

## 画像
🌐 [AutoDLイメージ](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)

### 言語切り替え
    .env設定ファイルでLANGUAGEパラメータを変更して、異なる言語に切り替えることができます。デフォルトは英語です（中国語：zh、英語：en、他の言語は後で追加されます）。

## 貢献

- 新しい貢献のための詳細なガイドラインを確認するには、[貢献方法](https://github.com/eosphoros-ai/DB-GPT/blob/main/CONTRIBUTING.md)を参照してください。

### 貢献者ウォール
<a href="https://github.com/eosphoros-ai/DB-GPT/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=eosphoros-ai/DB-GPT&max=200" />
</a>

## ライセンス
MITライセンス（MIT）

## 引用
もし`DB-GPT`があなたの研究や開発に役立つと感じた場合、以下の論文を引用してください。

DB-GPTの全体的なアーキテクチャについて知りたい場合は、<a href="https://arxiv.org/abs/2312.17449" target="_blank">論文</a>と<a href="https://arxiv.org/abs/2404.10209" target="_blank">論文</a>を引用してください。

DB-GPTを使用してAgent開発に関する内容について知りたい場合は、<a href="https://arxiv.org/abs/2412.13520" target="_blank">論文</a>を引用してください。 
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

## 連絡先情報
コミュニティを構築するために取り組んでいます。コミュニティの構築に関するアイデアがあれば、お気軽にお問い合わせください。
[![](https://dcbadge.vercel.app/api/server/7uQnPuveTY?compact=true&style=flat)](https://discord.gg/7uQnPuveTY)

[![Star History Chart](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)
