# OpenAI SDK Calls Local Multi-model
The call of multi-model services is compatible with the OpenAI interface, and the models deployed in DB-GPT can be directly called through the OpenAI SDK. 

:::info note

⚠️ Before using this project, you must first deploy the model service, which can be deployed through the [cluster deployment tutorial](/docs/latest/installation/model_service/cluster/).
:::


## Start apiserver

After deploying the model service, you need to start the API Server. By default, the model API Server uses port `8100` to start.
```bash
dbgpt start apiserver --controller_addr http://127.0.0.1:8000 --api_keys EMPTY

```


## Verify

### cURL validation
After the apiserver is started, the service call can be verified. First, let's look at verification through curl.


:::tip
List models
:::
```bash
curl http://127.0.0.1:8100/api/v1/models \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json"
```

:::tip
Chat
:::
```bash
curl http://127.0.0.1:8100/api/v1/chat/completions \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{"model": "vicuna-13b-v1.5", "messages": [{"role": "user", "content": "hello"}]}'
```

:::tip
Embedding 
:::
```bash
curl http://127.0.0.1:8100/api/v1/embeddings \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{
    "model": "text2vec",
    "input": "Hello world!"
}'
```


## Verify via OpenAI SDK

```bash
import openai
openai.api_key = "EMPTY"
openai.api_base = "http://127.0.0.1:8100/api/v1"
model = "vicuna-13b-v1.5"

completion = openai.ChatCompletion.create(
  model=model,
  messages=[{"role": "user", "content": "hello"}]
)
# print the completion
print(completion.choices[0].message.content)
```

## (Experimental) Rerank Open API

The rerank API is an experimental feature that can be used to rerank the candidate list. 

1. Use cURL to verify the rerank API.
```bash
curl http://127.0.0.1:8100/api/v1/beta/relevance \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{
    "model": "bge-reranker-base",
    "query": "what is awel talk about?",
    "documents": [
      "Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application development.",
      "Autonomous agents have long been a research focus in academic and industry communities",
      "AWEL is divided into three levels in deign, namely the operator layer, AgentFream layer and DSL layer.",
      "Elon musk is a famous entrepreneur and inventor, he is the founder of SpaceX and Tesla."
    ]
}'
```

2. Use python to verify the rerank API.
```python
from dbgpt.rag.embedding import OpenAPIRerankEmbeddings

rerank = OpenAPIRerankEmbeddings(api_key="EMPTY", model_name="bge-reranker-base")
rerank.predict(
    query="what is awel talk about?", 
    candidates=[
        "Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application development.",
        "Autonomous agents have long been a research focus in academic and industry communities",
        "AWEL is divided into three levels in deign, namely the operator layer, AgentFream layer and DSL layer.",
        "Elon musk is a famous entrepreneur and inventor, he is the founder of SpaceX and Tesla."
    ]
)
```

The output is as follows:
```bash
[
 0.9685816764831543,
 3.7338297261158004e-05,
 0.03692878410220146,
 3.73825132555794e-05
]
```
