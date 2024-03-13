# ProxyLLMs
DB-GPT can be deployed on servers with lower hardware through proxy LLMs, and now dbgpt support many proxy llms, such as OpenAI、Azure、Wenxin、Tongyi、Zhipu and so on.

### Proxy model

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI', value: 'openai'},
    {label: 'Azure', value: 'Azure'},
    {label: 'Qwen', value: 'qwen'},
    {label: 'ChatGLM', value: 'chatglm'},
    {label: 'WenXin', value: 'erniebot'},
  ]}>
  <TabItem value="openai" label="open ai">
  Install dependencies

```python
pip install  -e ".[openai]"
```

Download embedding model

```python
cd DB-GPT
mkdir models and cd models
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
LLM_MODEL=chatgpt_proxyllm
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
# If you use gpt-4
# PROXYLLM_BACKEND=gpt-4
```
  </TabItem>

  <TabItem value="Azure" label="Azure">
  Install dependencies

```python
pip install  -e ".[openai]"
```

Download embedding model

```python
cd DB-GPT
mkdir models and cd models
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese # change this to other embedding model if needed.
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
LLM_MODEL=proxyllm
PROXY_API_KEY=xxxx
PROXY_API_BASE=https://xxxxxx.openai.azure.com/
PROXY_API_TYPE=azure
PROXY_SERVER_URL=xxxx
PROXY_API_VERSION=2023-05-15
PROXYLLM_BACKEND=gpt-35-turbo
API_AZURE_DEPLOYMENT=xxxx[deployment_name]
```
  </TabItem>

  <TabItem value="qwen" label="通义千问">
Install dependencies

```python
pip install dashscope
```

Download embedding model

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
# Aliyun tongyiqianwen
LLM_MODEL=tongyi_proxyllm
TONGYI_PROXY_API_KEY={your-tongyi-sk}
PROXY_SERVER_URL={your_service_url}
```
  </TabItem>
  <TabItem value="chatglm" label="chatglm" >
Install dependencies

```python
pip install zhipuai
```

Download embedding model

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
LLM_MODEL=zhipu_proxyllm
PROXY_SERVER_URL={your_service_url}
ZHIPU_MODEL_VERSION={version}
ZHIPU_PROXY_API_KEY={your-zhipu-sk}
```
  </TabItem>

  <TabItem value="erniebot" label="文心一言" default>

Download embedding model

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large
```

Configure the proxy and modify LLM_MODEL, MODEL_VERSION, API_KEY and API_SECRET in the `.env`file

```python
# .env
LLM_MODEL=wenxin_proxyllm
WEN_XIN_MODEL_VERSION={version} # ERNIE-Bot or ERNIE-Bot-turbo
WEN_XIN_API_KEY={your-wenxin-sk}
WEN_XIN_API_SECRET={your-wenxin-sct}
```
  </TabItem>
</Tabs>


:::info note

⚠️ Be careful not to overwrite the contents of the `.env` configuration file
:::