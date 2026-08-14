<img src="./assets/LOGO_SMALL.png" alt="Logo" style="vertical-align: middle; height: 24px;" /> DB-GPT: AI Native Data App Development framework with AWEL and Agents

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

[**दस्तावेज़**](http://docs.dbgpt.cn/docs/overview/) | [**हमसे संपर्क करें**](https://github.com/eosphoros-ai/DB-GPT/blob/main/README.zh.md#%E8%81%94%E7%B3%BB%E6%88%91%E4%BB%AC) | [**समुदाय**](https://github.com/eosphoros-ai/community) | [**पेपर**](https://arxiv.org/pdf/2312.17449.pdf)

</div>

## DB-GPT क्या है?

🤖 **DB-GPT AWEL (Agentic Workflow Expression Language) और एजेंटों के साथ एक ओपन सोर्स AI नेटिव डेटा ऐप डेवलपमेंट फ्रेमवर्क है**। 

उद्देश्य बड़े मॉडलों के क्षेत्र में बुनियादी ढांचा बनाना है, मल्टी-मॉडल प्रबंधन (SMMF), Text2SQL प्रभाव अनुकूलन, RAG फ्रेमवर्क और अनुकूलन, मल्टी-एजेंट फ्रेमवर्क सहयोग, AWEL (एजेंट वर्कफ्लो ऑर्केस्ट्रेशन) आदि जैसे कई तकनीकी क्षमताओं के विकास के माध्यम से। जो बड़े मॉडल अनुप्रयोगों को डेटा के साथ सरल और अधिक सुविधाजनक बनाता है।

🚀 **डेटा 3.0 युग में, मॉडलों और डेटाबेस पर आधारित, उद्यम और डेवलपर्स कम कोड के साथ अपने खुद के विशेष अनुप्रयोग बना सकते हैं।**

### परिचय 
DB-GPT की वास्तुकला निम्नलिखित चित्र में दिखाई गई है:

<p align="center">
  <img src="./assets/dbgpt.png" width="800" />
</p>

कोर क्षमताओं में निम्नलिखित भाग शामिल हैं:

- **RAG (Retrieval Augmented Generation)**: RAG वर्तमान में सबसे व्यावहारिक रूप से कार्यान्वित और अत्यंत आवश्यक डोमेन है। DB-GPT ने पहले ही RAG पर आधारित एक फ्रेमवर्क लागू किया है, जो उपयोगकर्ताओं को DB-GPT की RAG क्षमताओं का उपयोग करके ज्ञान-आधारित अनुप्रयोग बनाने की अनुमति देता है।

- **GBI (Generative Business Intelligence)**: जनरेटिव BI DB-GPT परियोजना की कोर क्षमताओं में से एक है, जो उद्यम रिपोर्ट विश्लेषण और व्यावसायिक अंतर्दृष्टि बनाने के लिए आधारभूत डेटा बुद्धिमत्ता तकनीक प्रदान करता है।

- **फाइन-ट्यूनिंग फ्रेमवर्क**: मॉडल फाइन-ट्यूनिंग किसी भी उद्यम के लिए लंबवत और विशिष्ट डोमेन में कार्यान्वित करने के लिए एक अनिवार्य क्षमता है। DB-GPT एक पूर्ण फाइन-ट्यूनिंग फ्रेमवर्क प्रदान करता है जो DB-GPT परियोजना के साथ सहज रूप से एकीकृत होता है। हालिया फाइन-ट्यूनिंग प्रयासों में, स्पाइडर डेटासेट पर आधारित एक सटीकता दर 82.5% हासिल की गई है।

- **डेटा-ड्रिवन मल्टी-एजेंट फ्रेमवर्क**: DB-GPT एक डेटा-ड्रिवन स्व-विकासशील मल्टी-एजेंट फ्रेमवर्क प्रदान करता है, जिसका उद्देश्य निरंतर डेटा पर आधारित निर्णय लेना और निष्पादित करना है।

- **डेटा फैक्टरी**: डेटा फैक्टरी मुख्य रूप से बड़े मॉडलों के युग में विश्वसनीय ज्ञान और डेटा को साफ करने और संसाधित करने के बारे में है।

- **डेटा स्रोत**: विभिन्न डेटा स्रोतों को एकीकृत करना ताकि उत्पादन व्यावसायिक डेटा को DB-GPT की कोर क्षमताओं से सहज रूप से जोड़ा जा सके।

#### सबमॉड्यूल
- [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub) बड़े भाषा मॉडलों (LLMs) पर पर्यवेक्षित फाइन-ट्यूनिंग (SFT) लागू करके उच्च प्रदर्शन के साथ Text-to-SQL वर्कफ्लो।

- [dbgpts](https://github.com/eosphoros-ai/dbgpts)  dbgpts आधिकारिक रिपॉजिटरी है जिसमें कुछ डेटा ऐप्स, AWEL ऑपरेटर्स, AWEL वर्कफ्लो टेम्प्लेट और एजेंट शामिल हैं जो DB-GPT पर बनाए गए हैं।

#### डीपविकी
- [DB-GPT](https://deepwiki.com/eosphoros-ai/DB-GPT)
- [DB-GPT-HUB](https://deepwiki.com/eosphoros-ai/DB-GPT-Hub)
- [dbgpts](https://deepwiki.com/eosphoros-ai/dbgpts)


#### Text2SQL फाइनट्यून

  |     LLM     |  समर्थित  | 
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


[Text2SQL फाइनट्यून के बारे में अधिक जानकारी](https://github.com/eosphoros-ai/DB-GPT-Hub)

- [DB-GPT-Plugins](https://github.com/eosphoros-ai/DB-GPT-Plugins) DB-GPT प्लगइन्स जो Auto-GPT प्लगइन को सीधे चला सकते हैं
- [GPT-Vis](https://github.com/eosphoros-ai/GPT-Vis) विज़ुअलाइज़ेशन प्रोटोकॉल

### AI-नेटिव डेटा ऐप 
---
- 🔥🔥🔥 [रिलीज़ V0.7.0 | महत्वपूर्ण अपग्रेड का एक सेट](http://docs.dbgpt.cn/blog/db-gpt-v070-release)
  - [MCP प्रोटोकॉल का समर्थन](https://github.com/eosphoros-ai/DB-GPT/pull/2497)
  - [DeepSeek R1 का समर्थन](https://github.com/deepseek-ai/DeepSeek-R1)
  - [QwQ-32B का समर्थन](https://huggingface.co/Qwen/QwQ-32B)
  - [बुनियादी मॉड्यूल को रिफैक्टर करें]()
    - [dbgpt-app](./packages/dbgpt-app)
    - [dbgpt-core](./packages/dbgpt-core)
    - [dbgpt-serve](./packages/dbgpt-serve)
    - [dbgpt-client](./packages/dbgpt-client)
    - [dbgpt-accelerator](./packages/dbgpt-accelerator)
    - [dbgpt-ext](./packages/dbgpt-ext)
---

## क्यों DB-GPT?

### 1. एजेंटिक डेटा विश्लेषण
कार्यों की योजना बनाएं, कार्य को चरणों में विभाजित करें, टूल्स को कॉल करें, और विश्लेषण वर्कफ़्लो को अंत तक पूरा करें।
![csv_data_analysis_demo](https://github.com/user-attachments/assets/4921fa40-20f7-4a9c-b908-c0b4e7caa9d6)

### 2. स्वायत्त SQL + कोड निष्पादन
डेटा को क्वेरी करने, डेटासेट साफ़ करने, मेट्रिक्स की गणना करने और आउटपुट उत्पन्न करने के लिए SQL और कोड जenerate करें।
![agentic_write_code](https://github.com/user-attachments/assets/aeebc2b8-6c50-4ebb-96fd-07b860faa044)
![sql_query](https://github.com/user-attachments/assets/da45de20-3768-4f0d-ab20-e939ddf21361)

### 3. मल्टी-सोर्स डेटा एक्सेस
संरचित और असंरचित स्रोतों के साथ काम करें, जिसमें डेटाबेस, स्प्रेडशीट, दस्तावेज़ और नॉलेज बेस शामिल हैं।

### 4. स्किल्स-संचालित एक्स्टेंसिबिलिटी
डोमेन ज्ञान, विश्लेषण विधियों और निष्पादन वर्कफ़्लो को पुन: प्रयोज्य स्किल्स में पैकेज करें।

![import_github_skill](https://github.com/user-attachments/assets/39f39c36-a014-4a2e-8e14-b3af3f1d2f1c)

![agent_browse_use](https://github.com/user-attachments/assets/21864e9f-2179-4f6f-910f-18463ec2b46e)

### 5. सैंडबॉक्स्ड निष्पादन
सुरक्षित, अधिक विश्वसनीय विश्लेषण के लिए अलग-थलग वातावरण में कोड और टूल्स चलाएं।
![sandbox](https://github.com/user-attachments/assets/bfbd78e0-15e2-42ac-876f-5b91847aadc1)


## इंस्टॉलेशन / क्विक स्टार्ट 
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black)
![macOS](https://img.shields.io/badge/mac%20os-000000?style=for-the-badge&logo=macos&logoColor=F0F0F0)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)

[**उपयोग ट्यूटोरियल**](http://docs.dbgpt.cn/docs/overview)
- [**इंस्टॉल**](http://docs.dbgpt.cn/docs/installation)
  - [Docker](http://docs.dbgpt.cn/docs/installation/docker)
  - [सोर्स कोड](http://docs.dbgpt.cn/docs/installation/sourcecode)
- [**क्विकस्टार्ट**](http://docs.dbgpt.cn/docs/quickstart)
- [**अनुप्रयोग**](http://docs.dbgpt.cn/docs/operation_manual)
  - [डेवलपमेंट गाइड](http://docs.dbgpt.cn/docs/cookbook/app/data_analysis_app_develop) 
  - [ऐप उपयोग](http://docs.dbgpt.cn/docs/application/app_usage)
  - [AWEL फ्लो उपयोग](http://docs.dbgpt.cn/docs/application/awel_flow_usage)
- [**डिबगिंग**](http://docs.dbgpt.cn/docs/operation_manual/advanced_tutorial/debugging)
- [**उन्नत उपयोग**](http://docs.dbgpt.cn/docs/application/advanced_tutorial/cli)
  - [SMMF](http://docs.dbgpt.cn/docs/application/advanced_tutorial/smmf)
  - [फाइनट्यून](http://docs.dbgpt.cn/docs/application/fine_tuning_manual/dbgpt_hub)
  - [AWEL](http://docs.dbgpt.cn/docs/awel/tutorial)


## विशेषताएं

वर्तमान में, हमने अपनी वर्तमान क्षमताओं को प्रदर्शित करने के लिए कई प्रमुख विशेषताओं का परिचय दिया है:
- **प्राइवेट डोमेन Q&A & डेटा प्रोसेसिंग**

  DB-GPT परियोजना ज्ञान आधार निर्माण में सुधार करने और संरचित और असंरचित डेटा दोनों के कुशल भंडारण और पुनर्प्राप्ति को सक्षम करने के लिए डिज़ाइन की गई कार्यक्षमताओं की एक श्रृंखला प्रदान करती है। इन कार्यक्षमताओं में कई फ़ाइल स्वरूपों को अपलोड करने के लिए अंतर्निहित समर्थन, कस्टम डेटा एक्सट्रैक्शन प्लग-इन्स को एकीकृत करने की क्षमता, और बड़ी मात्रा में जानकारी को प्रभावी ढंग से प्रबंधित करने के लिए एकीकृत वेक्टर भंडारण और पुनर्प्राप्ति क्षमताएं शामिल हैं।

- **मल्टी-डेटा स्रोत & GBI (जनरेटिव बिजनेस इंटेलिजेंस)**

  DB-GPT परियोजना Excel, डेटाबेस और डेटा गोदाम सहित विविध डेटा स्रोतों के साथ सहज प्राकृतिक भाषा इंटरैक्शन को सुविधाजनक बनाती है। यह इन स्रोतों से जानकारी को क्वेरी और पुनर्प्राप्त करने की प्रक्रिया को सरल बनाता है, उपयोगकर्ताओं को सहज बातचीत में संलग्न होने और अंतर्दृष्टि प्राप्त करने में सक्षम बनाता है। इसके अलावा, DB-GPT विश्लेषणात्मक रिपोर्ट उत्पन्न करने का समर्थन करता है, उपयोगकर्ताओं को मूल्यवान डेटा सारांश और व्याख्याएं प्रदान करता है।

- **मल्टी-एजेंट और प्लगइन्स**

  यह विभिन्न कार्यों को करने के लिए कस्टम प्लग-इन्स का समर्थन प्रदान करता है और मूल रूप से Auto-GPT प्लग-इन मॉडल को एकीकृत करता है। एजेंट प्रोटोकॉल एजेंट प्रोटोकॉल मानक का पालन करता है।

- **स्वचालित फाइन-ट्यूनिंग text2SQL**

  हमने बड़े भाषा मॉडलों (LLMs), Text2SQL डेटासेट, LoRA/QLoRA/Pturning और अन्य फाइन-ट्यूनिंग विधियों पर केंद्रित एक स्वचालित फाइन-ट्यूनिंग हल्का फ्रेमवर्क विकसित किया है। यह फ्रेमवर्क Text-to-SQL फाइन-ट्यूनिंग को सरल बनाता है, इसे एक असेंबली लाइन प्रक्रिया जितना सरल बनाता है। [DB-GPT-Hub](https://github.com/eosphoros-ai/DB-GPT-Hub)

  - **SMMF (सर्विस-ओरिएंटेड मल्टी-मॉडल मैनेजमेंट फ्रेमवर्क)**

    हम व्यापक मॉडल समर्थन प्रदान करते हैं, जिसमें ओपन-सोर्स और API एजेंट दोनों से दर्जनों बड़े भाषा मॉडल (LLMs) शामिल हैं, जैसे LLaMA/LLaMA2, Baichuan, ChatGLM, Wenxin, Tongyi, Zhipu, और कई अन्य। 

  - समाचार
    <table>
      <thead>
        <tr>
          <th>प्रदाता</th>
          <th>समर्थित</th>
          <th>मॉडल</th>
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

- [अधिक समर्थित LLMs](http://docs.dbgpt.site/docs/modules/smmf)

- **गोपनीयता और सुरक्षा**
  
  हम विभिन्न तकनीकों के कार्यान्वयन के माध्यम से डेटा की गोपनीयता और सुरक्षा सुनिश्चित करते हैं, जिसमें निजीकरण बड़े मॉडल और प्रॉक्सी डेसेंसिटाइज़ेशन शामिल हैं।

- समर्थित डेटा स्रोत
  - [डेटा स्रोत](http://docs.dbgpt.cn/docs/modules/connections)

## छवि
🌐 [AutoDL छवि](https://www.codewithgpu.com/i/eosphoros-ai/DB-GPT/dbgpt)



## योगदान

- नए योगदान के लिए विस्तृत दिशानिर्देशों की जांच करने के लिए, कृपया [कैसे योगदान करें](https://github.com/eosphoros-ai/DB-GPT/blob/main/CONTRIBUTING.md) देखें

### योगदानकर्ता दीवार
<a href="https://github.com/eosphoros-ai/DB-GPT/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=eosphoros-ai/DB-GPT&max=200" />
</a>


## लाइसेंस
MIT लाइसेंस (MIT)

## डिस्क्लेमर
- [डिस्क्लेमर](./DISCKAIMER.md)

## उद्धरण
यदि आप DB-GPT की समग्र वास्तुकला को समझना चाहते हैं, तो कृपया <a href="https://arxiv.org/abs/2312.17449" target="_blank">पेपर</a> और <a href="https://arxiv.org/abs/2404.10209" target="_blank">पेपर</a> का उद्धरण करें

यदि आप एजेंट विकास के लिए DB-GPT का उपयोग सीखना चाहते हैं, तो कृपया <a href="https://arxiv.org/abs/2412.13520" target="_blank">पेपर</a> का उद्धरण करें
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


## संपर्क जानकारी
DB-GPT में योगदान करने वाले सभी लोगों को धन्यवाद! आपकी विचार, कोड, टिप्पणियां, और यहां तक कि घटनाओं और सोशल प्लेटफार्मों पर उन्हें साझा करना DB-GPT को बेहतर बना सकता है।
हम एक समुदाय बनाने पर काम कर रहे हैं, यदि आपके पास समुदाय बनाने के लिए कोई विचार हैं, तो कृपया हमसे संपर्क करें।  

- [GitHub मुद्दे](https://github.com/eosphoros-ai/DB-GPT/issues) ⭐️: GB-DPT का उपयोग करने के बारे में प्रश्नों के लिए, CONTRIBUTING देखें।  
- [GitHub चर्चाएं](https://github.com/orgs/eosphoros-ai/discussions) ⭐️: अपना अनुभव या अद्वितीय ऐप्स साझा करें।  
- [ट्विटर](https://x.com/DBGPT_AI) ⭐️: कृपया हमसे बात करने के लिए स्वतंत्र महसूस करें।  


[![स्टार इतिहास चार्ट](https://star-history.dera.page/svg?repos=csunny/DB-GPT&type=Date)](https://star-history.dera.page/#csunny/DB-GPT)