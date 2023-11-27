# OpenAI SDK Calls Local Multi-model
The call of multi-model services is compatible with the OpenAI interface, and the models deployed in DB-GPT can be directly called through the OpenAI SDK. 

:::info note

⚠️ Before using this project, you must first deploy the model service, which can be deployed through the [cluster deployment tutorial](/docs/installation/model_service/cluster).
:::


## Start apiserver

After deploying the model service, you need to start the API Server. By default, the model API Server uses port `8100` to start.
```python
dbgpt start apiserver --controller_addr http://127.0.0.1:8000 --api_keys EMPTY

```


## Verify

### cURL validation
After the apiserver is started, the service call can be verified. First, let's look at verification through curl.


:::tip
List models
:::
```python
curl http://127.0.0.1:8100/api/v1/models \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json"
```

:::tip
Chat
:::
```python
curl http://127.0.0.1:8100/api/v1/chat/completions \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{"model": "vicuna-13b-v1.5", "messages": [{"role": "user", "content": "hello"}]}'
```


## Verify via OpenAI SDK

```python
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

