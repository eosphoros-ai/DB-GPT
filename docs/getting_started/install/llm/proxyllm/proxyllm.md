Proxy LLM API
==================================
Now DB-GPT supports connect LLM service through proxy rest api.

LLM rest api now supports
```{note}
* OpenAI
* Azure
* Aliyun tongyi
* Baidu wenxin
* Zhipu
* Baichuan
* Bard
```


### How to Integrate LLM rest API, like OpenAI, Azure, tongyi, wenxin  llm api service?
update your `.env` file
```commandline
#OpenAI
LLM_MODEL=chatgpt_proxyllm
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions

#Azure
LLM_MODEL=chatgpt_proxyllm
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://xx.openai.azure.com/v1/chat/completions

#Aliyun tongyi
LLM_MODEL=tongyi_proxyllm
TONGYI_PROXY_API_KEY={your-tongyi-sk}
PROXY_SERVER_URL={your_service_url}

## Baidu wenxin
LLM_MODEL=wenxin_proxyllm
PROXY_SERVER_URL={your_service_url}
WEN_XIN_MODEL_VERSION={version}
WEN_XIN_API_KEY={your-wenxin-sk}
WEN_XIN_SECRET_KEY={your-wenxin-sct}

## Zhipu
LLM_MODEL=zhipu_proxyllm
PROXY_SERVER_URL={your_service_url}
ZHIPU_MODEL_VERSION={version}
ZHIPU_PROXY_API_KEY={your-zhipu-sk}

## Baichuan
LLM_MODEL=bc_proxyllm
PROXY_SERVER_URL={your_service_url}
BAICHUN_MODEL_NAME={version}
BAICHUAN_PROXY_API_KEY={your-baichuan-sk}
BAICHUAN_PROXY_API_SECRET={your-baichuan-sct}

## bard
LLM_MODEL=bard_proxyllm
PROXY_SERVER_URL={your_service_url}
# from https://bard.google.com/     f12-> application-> __Secure-1PSID
BARD_PROXY_API_KEY={your-bard-token}
```
```{tip}
Make sure your .env configuration is not overwritten
```

### How to Integrate Embedding rest API, like OpenAI, Azure api service?

```commandline
## Openai embedding model, See /pilot/model/parameter.py
EMBEDDING_MODEL=proxy_openai
proxy_openai_proxy_server_url=https://api.openai.com/v1
proxy_openai_proxy_api_key={your-openai-sk}
proxy_openai_proxy_backend=text-embedding-ada-002
```

