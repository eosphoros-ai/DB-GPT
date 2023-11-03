OpenAI-Compatible RESTful APIs
==================================
(openai-apis-index)=

### Install Prepare

You must [deploy DB-GPT cluster](https://db-gpt.readthedocs.io/en/latest/getting_started/install/cluster/vms/index.html) first.

### Launch Model API Server

```bash
dbgpt start apiserver --controller_addr http://127.0.0.1:8000 --api_keys EMPTY
```
By default, the Model API Server starts on port 8100.

### Validate with cURL

#### List models

```bash
curl http://127.0.0.1:8100/api/v1/models \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json"
```

#### Chat completions

```bash
curl http://127.0.0.1:8100/api/v1/chat/completions \
-H "Authorization: Bearer EMPTY" \
-H "Content-Type: application/json" \
-d '{"model": "vicuna-13b-v1.5", "messages": [{"role": "user", "content": "hello"}]}'
```

### Validate with OpenAI Official SDK

#### Chat completions

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