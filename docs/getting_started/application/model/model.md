Model Management
==================================
![model](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/4b160ee7-2e2a-4502-bd54-d7daa14b23e5)
DB-GPT Product Provides LLM Model Management in web interface.Including LLM Create, Start and Stop.
Now DB-GPT support LLMs:
```{admonition} Support LLMs
* Multi LLMs Support, Supports multiple large language models, currently supporting
  * [meta-llama/Llama-2-7b-chat-hf](https://huggingface.co/meta-llama/Llama-2-7b-chat-hf)
  * [baichuan2-7b/baichuan2-13b](https://huggingface.co/baichuan-inc)
  * [internlm/internlm-chat-7b](https://huggingface.co/internlm/internlm-chat-7b)
  * [Qwen/Qwen-7B-Chat/Qwen-14B-Chat](https://huggingface.co/Qwen/)
  * [Vicuna](https://huggingface.co/Tribbiani/vicuna-13b)
  * [BlinkDL/RWKV-4-Raven](https://huggingface.co/BlinkDL/rwkv-4-raven)
  * [camel-ai/CAMEL-13B-Combined-Data](https://huggingface.co/camel-ai/CAMEL-13B-Combined-Data)
  * [databricks/dolly-v2-12b](https://huggingface.co/databricks/dolly-v2-12b)
  * [FreedomIntelligence/phoenix-inst-chat-7b](https://huggingface.co/FreedomIntelligence/phoenix-inst-chat-7b)
  * [h2oai/h2ogpt-gm-oasst1-en-2048-open-llama-7b](https://huggingface.co/h2oai/h2ogpt-gm-oasst1-en-2048-open-llama-7b)
  * [lcw99/polyglot-ko-12.8b-chang-instruct-chat](https://huggingface.co/lcw99/polyglot-ko-12.8b-chang-instruct-chat)
  * [lmsys/fastchat-t5-3b-v1.0](https://huggingface.co/lmsys/fastchat-t5)
  * [mosaicml/mpt-7b-chat](https://huggingface.co/mosaicml/mpt-7b-chat)
  * [Neutralzz/BiLLa-7B-SFT](https://huggingface.co/Neutralzz/BiLLa-7B-SFT)
  * [nomic-ai/gpt4all-13b-snoozy](https://huggingface.co/nomic-ai/gpt4all-13b-snoozy)
  * [NousResearch/Nous-Hermes-13b](https://huggingface.co/NousResearch/Nous-Hermes-13b)
  * [openaccess-ai-collective/manticore-13b-chat-pyg](https://huggingface.co/openaccess-ai-collective/manticore-13b-chat-pyg)
  * [OpenAssistant/oasst-sft-4-pythia-12b-epoch-3.5](https://huggingface.co/OpenAssistant/oasst-sft-4-pythia-12b-epoch-3.5)
  * [project-baize/baize-v2-7b](https://huggingface.co/project-baize/baize-v2-7b)
  * [Salesforce/codet5p-6b](https://huggingface.co/Salesforce/codet5p-6b)
  * [StabilityAI/stablelm-tuned-alpha-7b](https://huggingface.co/stabilityai/stablelm-tuned-alpha-7b)
  * [THUDM/chatglm-6b](https://huggingface.co/THUDM/chatglm-6b)
  * [THUDM/chatglm2-6b](https://huggingface.co/THUDM/chatglm2-6b)
  * [tiiuae/falcon-40b](https://huggingface.co/tiiuae/falcon-40b)
  * [timdettmers/guanaco-33b-merged](https://huggingface.co/timdettmers/guanaco-33b-merged)
  * [togethercomputer/RedPajama-INCITE-7B-Chat](https://huggingface.co/togethercomputer/RedPajama-INCITE-7B-Chat)
  * [WizardLM/WizardLM-13B-V1.0](https://huggingface.co/WizardLM/WizardLM-13B-V1.0)
  * [WizardLM/WizardCoder-15B-V1.0](https://huggingface.co/WizardLM/WizardCoder-15B-V1.0)
  * [baichuan-inc/baichuan-7B](https://huggingface.co/baichuan-inc/baichuan-7B)
  * [HuggingFaceH4/starchat-beta](https://huggingface.co/HuggingFaceH4/starchat-beta)
  * [FlagAlpha/Llama2-Chinese-13b-Chat](https://huggingface.co/FlagAlpha/Llama2-Chinese-13b-Chat)
  * [BAAI/AquilaChat-7B](https://huggingface.co/BAAI/AquilaChat-7B)
  * [all models of OpenOrca](https://huggingface.co/Open-Orca)
  * [Spicyboros](https://huggingface.co/jondurbin/spicyboros-7b-2.2?not-for-all-audiences=true) + [airoboros 2.2](https://huggingface.co/jondurbin/airoboros-l2-13b-2.2)
  * [VMware&#39;s OpenLLaMa OpenInstruct](https://huggingface.co/VMware/open-llama-7b-open-instruct)

* Support API Proxy LLMs
  * [ChatGPT](https://api.openai.com/)
  * [Tongyi](https://www.aliyun.com/product/dashscope)
  * [Wenxin](https://cloud.baidu.com/product/wenxinworkshop?track=dingbutonglan)
  * [ChatGLM](http://open.bigmodel.cn/)
```
### Create && Start LLM Model
```{note}
Make sure your LLM Model file is downloaded or LLM Model Proxy api service is ready. 
```
![model-start](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/dacabcb9-92c6-43eb-95ed-8cabaa2d18e6)
 When create success, you can see:
![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/1b69bff6-8b37-493d-b6be-38f7b6e8ae2d)
Then you can choose and switch llm model service to chat.
![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/2d20eb6b-8976-4731-b433-373ac3383602)
### Stop LLM Model
![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/a21278d9-7bef-487b-bef1-460ce516b2f5)

