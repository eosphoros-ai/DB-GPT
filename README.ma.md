# <img src="./assets/LOGO_SMALL.png" alt="ലോഗോ" സ്റ്റൈൽ="ലംബ-അലൈൻ: മധ്യഭാഗം; ഉയരം: 24px;" /> DB-GPT: AWEL ഉം ഏജന്റുമാരുമൊത്തുള്ള AI നേറ്റീവ് ഡാറ്റ ആപ്പ് ഡെവലപ്‌മെന്റ് ഫ്രെയിംവർക്ക്

<p align="left">

<img src="./assets/dbgpt_vision.png" width="100%" />
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
<img alt="ഔദ്യോഗിക വെബ്‌സൈറ്റ്" src="https://img.shields.io/badge/Official%20website-DB--GPT-blue?style=flat&labelColor=3366CC" />
</a>
<a href="https://opensource.org/licenses/MIT">
<img alt="ലൈസൻസ്: MIT" src="https://img.shields.io/github/license/eosphoros-ai/db-gpt?style=flat&labelColor=009966&color=009933" />
</a>
<a href="https://github.com/eosphoros-ai/DB-GPT/releases">
      <img alt="റിലീസ് നോട്ടുകൾ" src="https://img.shields.io/github/v/release/eosphoros-ai/db-gpt?style=flat&labelColor=FF9933&color=FF6633" />
    </a>
    <a href="https://github.com/eosphoros-ai/DB-GPT/issues">
      <img alt="തുറന്ന പ്രശ്നങ്ങൾ" src="https://img.shields.io/github/issues-raw/eosphoros-ai/db-gpt?style=flat&labelColor=666666&color=333333" />
    </a>
    <a href="https://x.com/DBGPT_AI">
      <img alt="X (മുൻപ് ട്വിറ്റർ) പിന്തുടരുക" src="https://img.shields.io/twitter/follow/DBGPT_AI" />
    </a>
    <a href="https://medium.com/@dbgpt0506">
      <img alt="മീഡിയം പിന്തുടരുക" src="https://badgen.net/badge/Medium/DB-GPT/333333?icon=medium&labelColor=666666" />
    </a>
    <a href="https://space.bilibili.com/3537113070963392">
      <img alt="ബിലിബിലി സ്പേസ്" src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.bilibili.com%2Fx%2Frelation%2Fstat%3Fvmid%3D3537113070963392&query=data.follower&style=flat&logo=bilibili&logoColor=white&label=Bilibili%20Fans&labelColor=F37697&color=6495ED" />
    </a>
    <a href="https://join.slack.com/t/slack-inu2564/shared_invite/zt-29rcnyw2b-N~ubOD9kFc7b7MDOAM1otA">
      <img alt="സ്ലാക്ക്" src="https://img.shields.io/badge/Slack-Join%20us-5d6b98?style=flat&logo=slack&labelColor=7d89b0" />
    </a>
    <a href="https://codespaces.new/eosphoros-ai/DB-GPT">
      <img alt="ഗിറ്റ്ഹബ് കോഡ്സ്പേസുകളിൽ തുറക്കുക" src="https://github.com/codespaces/badge.svg" />
    </a>
  </p>


[![English](https://img.shields.io/badge/English-d9d9d9?style=flat-square)](README.md)
[![简体中文](https://img.shields.io/badge/简体中文-d9d9d9?style=flat-square)](README.zh.md)
[![日本語](https://img.shields.io/badge/日本語-d9d9d9?style=flat-square)](README.ja.md) 

[**രേഖകൾ**](http://docs.dbgpt.cn/docs/overview/) | [**ഞങ്ങളെ സമീപിക്കുക**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**സമൂഹം**](https://github.com/eosphoros-ai/community) | [**പേപ്പർ**](https://arxiv.org/pdf/2312.17449.pdf)

</div>

## DB-GPT എന്താണ്?

🤖 **DB-GPT എന്നത് AWEL (Agentic Workflow Expression Language) മറ്റും ഏജന്റുകളും ഉൾപ്പെടുന്ന ഒരു ഓപ്പൺ സോഴ്സ് AI നേറ്റീവ് ഡാറ്റ ആപ്പ് ഡെവലപ്മെന്റ് ഫ്രെയിംവർക്കാണ്**.

ലക്ഷ്യം വലിയ മോഡലുകളുടെ മേഖലയിൽ ഇൻഫ്രാസ്ട്രക്ചർ നിർമ്മിക്കുക എന്നതാണ്, മൾട്ടി-മോഡൽ മാനേജ്മെന്റ് (SMMF), Text2SQL ഇഫക്ട് ഒപ്റ്റിമൈസേഷൻ, RAG ഫ്രെയിംവർക്ക് മറ്റും ഒപ്റ്റിമൈസേഷൻ, മൾട്ടി-ഏജന്റുകൾ ഫ്രെയിംവർക്ക് സഹകരണം, AWEL (ഏജന്റ് വർക്ക്ഫ്ലോ ഓർക്കസ്ട്രേഷൻ) എന്നിവ പോലുള്ള ഒന്നിലധികം സാങ്കേതിക കഴിവുകളുടെ വികസനത്തിലൂടെ. ഇത് വലിയ മോഡൽ ആപ്ലിക്കേഷനുകളെ ഡാറ്റയോടെ ലളിതവും സൗകര്യപ്രദവുമാക്കുന്നു.

🚀 **ഡാറ്റ 3.0 യുഗത്തിൽ, മോഡലുകളും ഡാറ്റാബേസുകളും അടിസ്ഥാനമാക്കി, എന്റർപ്രൈസുകളും ഡെവലപ്പർമാരും കുറച്ച് കോഡോടെ അവരുടെ സ്വന്തം വിശേഷിത ആപ്ലിക്കേഷനുകൾ നിർമ്മിക്കാൻ കഴിയും.**

### ആമുഖം
DB-GPT-യുടെ ആർക്കിടെക്ചർ ഇനിപ്പറയുന്ന ചിത്രത്തിൽ കാണിച്ചിരിക്കുന്നു:

<p align="center">
  <img src="./assets/dbgpt.png" width="800" />
</p>

കോർ കഴിവുകൾ ഇനിപ്പറയുന്ന ഭാഗങ്ങളെ ഉൾക്കൊള്ളുന്നു:

- **RAG (Retrieval Augmented Generation)**: RAG നിലവിൽ ഏറ്റവും പ്രായോഗികമായി നടപ്പിലാക്കിയതും അത്യാവശ്യമായതുമായ ഡൊമെയ്നാണ്. DB-GPT ഇതിനകം RAG അടിസ്ഥാനമാക്കിയ ഒരു ഫ്രെയിംവർക്ക് നടപ്പിലാക്കിയിട്ടുണ്ട്, ഇത് ഉപയോക്താക്കൾക്ക് DB-GPT-യുടെ RAG കഴിവുകൾ ഉപയോഗിച്ച് അറിവ് അടിസ്ഥാനമാക്കിയ ആപ്ലിക്കേഷനുകൾ നിർമ്മിക്കാൻ അനുവദിക്കുന്നു.

- **GBI (Generative Business Intelligence)**: ജനറേറ്റീവ് BI, DB-GPT പ്രോജക്റ്റിന്റെ കോർ കഴിവുകളിൽ ഒന്നാണ്, എന്റർപ്രൈസ് റിപ്പോർട്ട് അനലിസിസ് മറ്റും ബിസിനസ് ഇൻസൈറ്റുകൾ നിർമ്മിക്കുന്നതിനുള്ള അടിസ്ഥാന ഡാറ്റ ഇന്റലിജൻസ് സാങ്കേതികത നൽകുന്നു.

- **ഫൈൻ-ട്യൂണിംഗ് ഫ്രെയിംവർക്ക്**: മോഡൽ ഫൈൻ-ട്യൂണിംഗ് എന്നത് ഏതൊരു എന്റർപ്രൈസും വർട്ടിക്കൽ മറ്റും നിഷ് ഡൊമെയ്നുകളിൽ നടപ്പിലാക്കേണ്ടത് അനിവാര്യമായ കഴിവാണ്. DB-GPT ഒരു പൂർണ്ണ ഫൈൻ-ട്യൂണിംഗ് ഫ്രെയിംവർക്ക് നൽകുന്നു, ഇത് DB-GPT പ്രോജക്റ്റുമായി തടസ്സമില്ലാതെ സംയോജിപ്പിക്കുന്നു. സമീപകാല ഫൈൻ-ട്യൂണിംഗ് ശ്രമങ്ങളിൽ, Spider ഡാറ്റാസെറ്റ് അടിസ്ഥാനമാക്കി 82.5% അക്യുറസി നിരക്ക് നേടിയിട്ടുണ്ട്.

- **ഡാറ്റ-ഡ്രൈവൻ മൾട്ടി-ഏജന്റുകൾ ഫ്രെയിംവർക്ക്**: DB-GPT ഒരു ഡാറ്റ-ഡ്രൈവൻ സെൽഫ്-ഇവോൾവിംഗ് മൾട്ടി-ഏജന്റുകൾ ഫ്രെയിംവർക്ക് നൽകുന്നു, ഇത് ഡാറ്റയെ അടിസ്ഥാനമാക്കി തുടർച്ചയായി തീരുമാനങ്ങൾ എടുത്ത് നടപ്പിലാക്കാൻ ലക്ഷ്യമിടുന്നു.

- **ഡാറ്റ ഫാക്ടറി**: ഡാറ്റ ഫാക്ടറി പ്രധാനമായും വലിയ മോഡലുകളുടെ യുഗത്തിൽ വിശ്വസ്ത അറിവും ഡാറ്റയും ക്ലീൻ ചെയ്യുന്നതും പ്രോസസ്സ് ചെയ്യുന്നതുമാണ്.

- **ഡാറ്റ സോഴ്സുകൾ**: വിവിധ ഡാറ്റ സോഴ്സുകൾ സംയോജിപ്പിച്ച് പ്രൊഡക്ഷൻ ബിസിനസ് ഡാറ്റ DB-GPT-യുടെ കോർ കഴിവുകളിലേക്ക് തടസ്സമില്ലാതെ കണക്ട് ചെയ്യുന്നു.

#### സബ്മോഡ്യൂൾ
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) ലാർജ് ലാംഗ്വേജ് മോഡലുകളിൽ (LLMs) സൂപ്പർവൈസ്ഡ് ഫൈൻ-ട്യൂണിംഗ് (SFT) പ്രയോഗിച്ച് ഉയർന്ന പ്രകടനം ഉള്ള Text-to-SQL വർക്ക്ഫ്ലോ.

- [dbgpts](https://github.com/eosphoros-ai/dbgpts)  dbgpts എന്നത് ഔദ്യോഗിക റിപ്പോസിറ്ററിയാണ്, ഇത് DB-GPT-യിൽ നിർമ്മിച്ച ചില ഡാറ്റ ആപ്പുകൾ, AWEL ഓപ്പറേറ്റർമാർ, AWEL വർക്ക്ഫ്ലോ ടെംപ്ലേറ്റുകൾ മറ്റും ഏജന്റുകൾ ഉൾക്കൊള്ളുന്നു.

#### ഡീപ്വിക്കി
- [DB-GPT](https://deepwiki.com/eosphoros-ai/DB-GPT)
- [DB-GPT-HUB](https://deepwiki.com/eosphoros-ai/DB-GPT-Hub)
- [dbgpts](https://deepwiki.com/eosphoros-ai/dbgpts)


#### Text2SQL ഫൈൻട്യൂൺ

  |     LLM     |  പിന്തുണയ്ക്കുന്നു  | 
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

[Text2SQL ഫൈൻട്യൂണിനെക്കുറിച്ച് കൂടുതൽ വിവരങ്ങൾ](https://github.com/eosphoros-ai/DB-GPT-Hub)

- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT പ്ലഗിനുകൾ, Auto-GPT പ്ലഗിൻ നേരിട്ട് പ്രവർത്തിപ്പിക്കാൻ കഴിയും
- [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) വിഷ്വലൈസേഷൻ പ്രോട്ടോക്കോൾ

### AI-നേറ്റീവ് ഡാറ്റ ആപ്പ് 
---
- 🔥🔥🔥 [V0.7.0 റിലീസ് ചെയ്തു | ഒരു കൂട്ടം പ്രധാന അപ്ഗ്രേഡുകൾ](http://docs.dbgpt.cn/blog/db-gpt-v070-release)
  - [MCP പ്രോട്ടോക്കോൾ പിന്തുണയ്ക്കുക](https://github.com/eosphoros-ai/DB-GPT/pull/2497)
  - [DeepSeek R1 പിന്തുണയ്ക്കുക](https://github.com/deepseek-ai/DeepSeek-R1)
  - [QwQ-32B പിന്തുണയ്ക്കുക](https://huggingface.co/Qwen/QwQ-32B)
  - [അടിസ്ഥാന മൊഡ്യൂളുകൾ റിഫാക്ടർ ചെയ്യുക]()
    - [dbgpt-app](./packages/dbgpt-app)
    - [dbgpt-core](./packages/dbgpt-core)
    - [dbgpt-serve](./packages/dbgpt-serve)
    - [dbgpt-client](./packages/dbgpt-client)
    - [dbgpt-accelerator](./packages/dbgpt-accelerator)
    - [dbgpt-ext](./packages/dbgpt-ext)
---

## എന്തിനാണ് DB-GPT?

### 1. ഏജന്റ് അധിഷ്ഠിത ഡാറ്റാ അനലിസിസ്
ടാസ്ക്കുകൾ പ്ലാൻ ചെയ്യുക, വര്ക്ക് സ്റ്റെപ്പുകളായി വിഭജിക്കുക, ടൂളുകൾ വിളിക്കുക, അനലിസിസ് വർക്ക്ഫ്ലോകൾ അവസാനിപ്പിക്കുക.
![csv_data_analysis_demo](https://github.com/user-attachments/assets/4921fa40-20f7-4a9c-b908-c0b4e7caa9d6)

### 2. സ്വയംപ്രവര്ത്തിക്കുന്ന SQL + കോഡ് എക്സിക്യൂഷന്‍
ഡാറ്റ ചോദിക്കാനും ഡാറ്റാസെറ്റുകൾ വൃത്തിയാക്കാനും മെട്രിക്കുകൾ കണക്കാക്കാനും ഔട്ട്പുട്ട്കൾ ഉത്പാദിപ്പിക്കാനും SQLഉം കോഡും സൃഷ്ടിക്കുക.
![agentic_write_code](https://github.com/user-attachments/assets/aeebc2b8-6c50-4ebb-96fd-07b860faa044)
![sql_query](https://github.com/user-attachments/assets/da45de20-3768-4f0d-ab20-e939ddf21361)

### 3. മൾട്ടി-സോഴ്സ് ഡാറ്റ ആക്സസ്
സ്ട്രക്ചേഡും അൺസ്ട്രക്ചേഡുമായ സോഴ്സുകളിലൂടെ പ്രവർത്തിക്കുക, ഡാറ്റാബേസുകൾ, സ്പ്രഡ്ഷീറ്റുകൾ, ഡോക്യുമെന്റുകളും നോളജ് ബേസുകളും ഉൾപ്പെടുന്നു.

### 4. സ്കില്ല്-ഡ്രിവന്‍ എക്സ്റ്റെംസിബിലിറ്റി
ഡൊമെയ്‌ന്‍ അറിവ്, അനലിസിസ് രീതികളും എക്സിക്യൂഷന്‍ വർക്ക്ഫ്ലോകളും പുനരുപയോഗിക്കാവുന്ന സ്കില്ലുകളായി പാക്കേജ് ചെയ്യുക.

![import_github_skill](https://github.com/user-attachments/assets/39f39c36-a014-4a2e-8e14-b3af3f1d2f1c)

![agent_browse_use](https://github.com/user-attachments/assets/21864e9f-2179-4f6f-910f-18463ec2b46e)

### 5. സാന്ഡ്ബോക്സ് എക്സിക്യൂഷന്‍
കൂടുതൽ സുരക്ഷിതവും കൂടുതൽ വിശ്വസനീയവുമായ അനലിസിസിനായി ഐസോലേറ്റഡ് എൻവയോണ്മെന്റിൽ കോഡും ടൂളുകളും റൺ ചെയ്യുക.
![sandbox](https://github.com/user-attachments/assets/bfbd78e0-15e2-42ac-876f-5b91847aadc1)


## ഇൻസ്റ്റലേഷൻ / ക്വിക്ക് സ്റ്റാർട്ട് 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**ഉപയോഗ ട്യൂട്ടോറിയൽ**](http://docs.dbgpt.cn/docs/overview)
- [**ഇൻസ്റ്റാൾ ചെയ്യുക**](http://docs.dbgpt.cn/docs/installation)
  - [Docker](http://docs.dbgpt.cn/docs/installation/docker)
  - [സോഴ്സ് കോഡ്](http://docs.dbgpt.cn/docs/getting-started/deploy/source-code)
- [**ക്വിക്ക്‌സ്റ്റാർട്ട്**](http://docs.dbgpt.cn/docs/overview)
- [**അപ്ലിക്കേഷൻ**](http://docs.dbgpt.cn/docs/use_cases)
  - [ഡെവലപ്‌മെന്റ് ഗൈഡ്](http://docs.dbgpt.cn/docs/cookbook/app/data_analysis_app_develop) 
  - [AWEL ഫ്ളോ ഉപയോഗം](http://docs.dbgpt.cn/docs/application/awel_flow_usage)
- [**ഡീബഗ്ഗിംഗ്**](http://docs.dbgpt.cn/docs/operation_manual/advanced_tutorial/debugging)
- [**അഡ്വാൻസ്ഡ് ഉപയോഗം**](http://docs.dbgpt.cn/docs/application/advanced_tutorial/cli)
  - [SMMF](http://docs.dbgpt.cn/docs/application/advanced_tutorial/smmf)
  - [ഫൈൻട്യൂൺ](http://docs.dbgpt.cn/docs/application/fine_tuning_manual/dbgpt_hub)
  - [AWEL](http://docs.dbgpt.cn/docs/awel/tutorial)


## സവിശേഷതകൾ

ഇപ്പോൾ, ഞങ്ങളുടെ നിലവിലെ കഴിവുകൾ പ്രദർശിപ്പിക്കുന്നതിനായി നിരവധി പ്രധാന സവിശേഷതകൾ ഞങ്ങൾ അവതരിപ്പിച്ചിട്ടുണ്ട്:
- **സ്വകാര്യ ഡൊമെയ്ൻ Q&A & ഡാറ്റാ പ്രോസസ്സിംഗ്**

  DB-GPT പ്രോജക്റ്റ് നോളജ് ബേസ് നിർമ്മാണം മെച്ചപ്പെടുത്താനും സ്ട്രക്ചർഡ് മറ്റെങ്കിലും അൻസ്ട്രക്ചർഡ് ഡാറ്റയുടെ കാര്യക്ഷമമായ സംഭരണവും വീണ്ടെടുക്കലും സാധ്യമാക്കാനും രൂപകൽപ്പന ചെയ്തിരിക്കുന്ന നിരവധി പ്രവർത്തനങ്ങൾ വാഗ്ദാനം ചെയ്യുന്നു. ഇവയിൽ മൾട്ടിപ്പിൾ ഫയൽ ഫോർമാറ്റുകൾ അപ്‌ലോഡ് ചെയ്യുന്നതിനുള്ള ബിൽറ്റ്-ഇൻ സപ്പോർട്ട്, കസ്റ്റം ഡാറ്റാ എക്സ്ട്രാക്ഷൻ പ്ലഗ്-ഇൻസ് സംയോജിപ്പിക്കാനുള്ള കഴിവ്, മറ്റെങ്കിലും വലിയ അളവിലുള്ള വിവരങ്ങൾ ഫലപ്രദമായി നിയന്ത്രിക്കുന്നതിനുള്ള യൂണിഫൈഡ് വെക്ടർ സംഭരണവും വീണ്ടെടുക്കലും ഉൾപ്പെടുന്നു.

- **മൾട്ടി-ഡാറ്റാ സോഴ്സ് & GBI(ജെനറേറ്റീവ് ബിസിനസ് ഇന്റലിജൻസ്)**

  DB-GPT പ്രോജക്റ്റ് Excel, ഡാറ്റാബേസുകൾ, മറ്റെങ്കിലും ഡാറ്റാ വെയർഹൗസുകൾ എന്നിവയുൾപ്പെടെയുള്ള വൈവിധ്യമാർന്ന ഡാറ്റാ സോഴ്സുകളുമായി സീംലെസ് നാച്ചുറൽ ലാംഗ്വേജ് ഇന്ററാക്ഷൻ സാധ്യമാക്കുന്നു. ഇത് ഈ സോഴ്സുകളിൽ നിന്ന് വിവരങ്ങൾ ചോദ്യം ചെയ്യാനും വീണ്ടെടുക്കാനുമുള്ള പ്രക്രിയയെ ലളിതമാക്കുന്നു, ഉപയോക്താക്കളെ ഇന്റ്യൂട്ടീവ് സംഭാഷണങ്ങളിൽ പങ്കെടുക്കാനും ഇൻസൈറ്റുകൾ നേടാനും പ്രാപ്തരാക്കുന്നു. കൂടാതെ, DB-GPT അനലിറ്റിക്കൽ റിപ്പോർട്ടുകളുടെ ജനറേഷൻ സപ്പോർട്ട് ചെയ്യുന്നു, ഉപയോക്താക്കൾക്ക് മൂല്യവത്തായ ഡാറ്റാ സമ്മറികളും വ്യാഖ്യാനങ്ങളും നൽകുന്നു.

- **മൾട്ടി-ഏജന്റ്സ് & പ്ലഗ്-ഇൻസ്**

  ഇത് വിവിധ ടാസ്ക്കുകൾ നിർവ്വഹിക്കുന്നതിനായി കസ്റ്റം പ്ലഗ്-ഇൻസ് സപ്പോർട്ട് വാഗ്ദാനം ചെയ്യുന്നു, മറ്റെങ്കിലും Auto-GPT പ്ലഗ്-ഇൻ മോഡൽ നേറ്റീവ് ആയി സംയോജിപ്പിച്ചിരിക്കുന്നു. ഏജന്റ്സ് പ്രോട്ടോക്കോൾ ഏജന്റ് പ്രോട്ടോക്കോൾ സ്റ്റാൻഡേർഡ് പാലിക്കുന്നു.

- **ഓട്ടോമേറ്റഡ് ഫൈൻ-ട്യൂണിംഗ് text2SQL**

  ഞങ്ങൾ ലാർജ് ലാംഗ്വേജ് മോഡലുകൾ (LLMs), Text2SQL ഡാറ്റാസെറ്റുകൾ, LoRA/QLoRA/Pturning, മറ്റെങ്കിലും ഫൈൻ-ട്യൂണിംഗ് രീതികൾ എന്നിവയെ കേന്ദ്രീകരിച്ച് ഒരു ഓട്ടോമേറ്റഡ് ഫൈൻ-ട്യൂണിംഗ് ലൈറ്റ്‌വെയ്റ്റ് ഫ്രെയിംവർക്ക് വികസിപ്പിച്ചിട്ടുണ്ട്. ഈ ഫ്രെയിംവർക്ക് Text-to-SQL ഫൈൻ-ട്യൂണിംഗ് ലളിതമാക്കുന്നു, അത് ഒരു അസംബ്ലി ലൈൻ പ്രക്രിയയെപ്പോലെ സ്ട്രെയ്റ്റ്‌ഫോർവേഡ് ആക്കുന്നു. [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub)

  - **SMMF(സർവീസ്-ഓറിയന്റഡ് മൾട്ടി-മോഡൽ മാനേജ്മെന്റ് ഫ്രെയിംവർക്ക്)**

    ഞങ്ങൾ വിപുലമായ മോഡൽ സപ്പോർട്ട് വാഗ്ദാനം ചെയ്യുന്നു, LLaMA/LLaMA2, Baichuan, ChatGLM, Wenxin, Tongyi, Zhipu, മറ്റെങ്കിലും പോലുള്ള ഓപ്പൺ-സോഴ്സ് മറ്റെങ്കിലും API ഏജന്റുകളിൽ നിന്നുള്ള ഡസൻ കണക്കിന് ലാർജ് ലാംഗ്വേജ് മോഡലുകൾ (LLMs) ഉൾപ്പെടുന്നു. 

  - വാർത്തകൾ

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

- [കൂടുതൽ പിന്തുണയ്ക്കുന്ന LLMs](http://docs.dbgpt.cn/docs/modules/smmf)

- **സ്വകാര്യതയും സുരക്ഷയും**
  
  വിവിധ സാങ്കേതിക വിദ്യകൾ നടപ്പിലാക്കുന്നതിലൂടെ ഡാറ്റയുടെ സ്വകാര്യതയും സുരക്ഷയും ഞങ്ങൾ ഉറപ്പാക്കുന്നു, ഇതിൽ സ്വകാര്യമാക്കിയ വലിയ മോഡലുകളും പ്രോക്സി ഡിസെൻസിറ്റൈസേഷനും ഉൾപ്പെടുന്നു.

- പിന്തുണയ്ക്കുന്ന ഡാറ്റാസോഴ്സുകൾ
  - [ഡാറ്റാസോഴ്സുകൾ](http://docs.dbgpt.cn/docs/modules/connections)

## ഇമേജ്
🌐 [AutoDL ഇമേജ്](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)



## സംഭാവന

- പുതിയ സംഭാവനകൾക്കുള്ള വിശദമായ മാർഗ്ഗനിർദ്ദേശങ്ങൾ പരിശോധിക്കാൻ, ദയവായി [സംഭാവന ചെയ്യുന്നതെങ്ങനെ](https://github.com/eosphoros-ai/DB-GPT/blob/main/CONTRIBUTING.md) എന്നതിലേക്ക് പരിശോധിക്കുക

### സംഭാവകരുടെ വാൾ
<a href="https://github.com/eosphoros-ai/DB-GPT/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=eosphoros-ai/DB-GPT&max=200" />
</a>


## ലൈസൻസ്
The MIT License (MIT)

## ഡിസ്ക്ലെയിമർ
- [ഡിസ്ക്ലെയിമർ](./DISCLAIMER.md)

## സൈറ്റേഷൻ
DB-GPT-യുടെ മൊത്തം ആർക്കിടെക്ചർ മനസ്സിലാക്കാൻ നിങ്ങൾ ആഗ്രഹിക്കുന്നുവെങ്കിൽ, ദയവായി <a href="https://arxiv.org/abs/2312.17449" target="_blank">പേപ്പർ</a> മറ്റെങ്കിലും <a href="https://arxiv.org/abs/2404.10209" target="_blank">പേപ്പർ</a> സൈറ്റ് ചെയ്യുക

ഏജന്റ് ഡെവലപ്‌മെന്റിനായി DB-GPT ഉപയോഗിക്കുന്നതിനെക്കുറിച്ച് പഠിക്കാൻ നിങ്ങൾ ആഗ്രഹിക്കുന്നുവെങ്കിൽ, ദയവായി <a href="https://arxiv.org/abs/2412.13520" target="_blank">പേപ്പർ</a> സൈറ്റ് ചെയ്യുക
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


## കോൺടാക്റ്റ് വിവരം
DB-GPT-യിലേക്ക് സംഭാവന ചെയ്ത എല്ലാവർക്കും നന്ദി! നിങ്ങളുടെ ആശയങ്ങൾ, കോഡ്, അഭിപ്രായങ്ങൾ, മറ്റെങ്കിലും ഇവന്റുകളിലും സോഷ്യൽ പ്ലാറ്റ്ഫോമുകളിലും പങ്കിടുന്നത് DB-GPT-യെ മെച്ചപ്പെടുത്തും.
ഞങ്ങൾ ഒരു കമ്മ്യൂണിറ്റി നിർമ്മിക്കുന്നതിൽ പ്രവർത്തിക്കുന്നു, കമ്മ്യൂണിറ്റി നിർമ്മിക്കുന്നതിനുള്ള എന്തെങ്കിലും ആശയങ്ങൾ നിങ്ങൾക്കുണ്ടെങ്കിൽ, ഞങ്ങളെ സമീപിക്കാൻ മടിക്കരുത്.  

- [Github ഇഷ്യൂകൾ](https://github.com/eosphoros-ai/DB-GPT/issues) ⭐️：GB-DPT ഉപയോഗിക്കുന്നതിനെക്കുറിച്ചുള്ള ചോദ്യങ്ങൾക്ക്, CONTRIBUTING എന്നതിൽ കാണുക.  
- [Github ചർച്ചകൾ](https://github.com/orgs/eosphoros-ai/discussions) ⭐️：നിങ്ങളുടെ അനുഭവം അല്ലെങ്കിൽ അദ്വിതീയ ആപ്പുകൾ പങ്കിടുക.  
- [ട്വിറ്റർ](https://x.com/DBGPT_AI) ⭐️：ദയവായി ഞങ്ങളോട് സംസാരിക്കാൻ മടിക്കരുത്.  


[![സ്റ്റാർ ചരിത്ര ചാർട്ട്](https://api.star-history.com/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.com/#csunny/DB-GPT)

