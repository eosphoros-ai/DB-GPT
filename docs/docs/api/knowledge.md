# Knowledge

Get started with the Knowledge API

# Chat Knowledge Space

```python
POST /api/v2/chat/completions
```
### Examples

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### Chat Knowledge


<Tabs
  defaultValue="python"
  groupId="chat"
  values={[
    {label: 'Curl', value: 'curl'},
    {label: 'Python', value: 'python'},
  ]
}>

<TabItem value="curl">

```shell
DBGPT_API_KEY=dbgpt
SPACE_NAME={YOUR_SPACE_NAME}

curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"chatgpt_proxyllm\", \"chat_mode\": \"chat_knowledge\", \"chat_param\": \"$SPACE_NAME\"}"
```
 </TabItem>

<TabItem value="python">

```python
from dbgpt.client import Client

DBGPT_API_KEY = "dbgpt"
SPACE_NAME="{YOUR_SPACE_NAME}"

client = Client(api_key=DBGPT_API_KEY)

async for data in client.chat_stream(
    messages="Introduce AWEL", 
    model="chatgpt_proxyllm", 
    chat_mode="chat_knowledge", 
    chat_param=SPACE_NAME
):
    print(data)
```
 </TabItem>
</Tabs>

#### Chat Completion Response
```json
{
    "id": "acb050ab-eb2c-4754-97e4-6f3b94b7dac2",
    "object": "chat.completion",
    "created": 1710917272,
    "model": "chatgpt_proxyllm",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Agentic Workflow Expression Language (AWEL) is a specialized language designed for developing large model applications with intelligent agent workflows. It offers flexibility and functionality, allowing developers to focus on business logic for LLMs applications without getting bogged down in model and environment details. AWEL uses a layered API design architecture, making it easier to work with. You can find examples and source code to get started with AWEL, and it supports various operators and environments. AWEL is a powerful tool for building native data applications through workflows and agents."
            },
            "finish_reason": null
        }
    ],
    "usage": {
        "prompt_tokens": 0,
        "total_tokens": 0,
        "completion_tokens": 0
    }
}
```

#### Chat Completion Stream Response
```commandline
data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "AW"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "EL"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ","}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " which"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " stands"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " for"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " Ag"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "entic"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " Workflow"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " Expression"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " Language"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ","}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " is"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " a"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " powerful"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " tool"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " designed"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " for"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " developing"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " large"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " model"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " applications"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "."}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " It"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " simpl"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "ifies"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " the"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " process"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " by"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " allowing"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " developers"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " to"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " focus"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " on"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " business"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " logic"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " without"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " getting"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " bog"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "ged"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " down"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " in"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " complex"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " model"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " and"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " environment"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " details"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "."}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " AW"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "EL"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " offers"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " great"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " functionality"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " and"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " flexibility"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " through"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " its"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " layered"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " API"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " design"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " architecture"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "."}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " It"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " provides"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " a"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " set"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " of"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " intelligent"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " agent"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " workflow"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " expression"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " language"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " that"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " enhances"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " efficiency"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " in"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " application"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " development"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "."}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " If"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " you"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " want"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " to"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " learn"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " more"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " about"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " AW"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "EL"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ","}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " you"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " can"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " check"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " out"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " the"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " built"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "-in"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " examples"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " and"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " resources"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " available"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " on"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " platforms"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " like"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " Github"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ","}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " Docker"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "hub"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": ","}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " and"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " more"}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "."}}]}

data: {"id": "chatcmpl-86f60a0c-e686-11ee-9322-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "\n\n<references title=\"References\" references=\"[{&quot;name&quot;: &quot;AWEL_URL&quot;, &quot;chunks&quot;: [{&quot;id&quot;: 2526, &quot;content&quot;: &quot;Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model applicationdevelopment. It provides great functionality and flexibility. Through the AWEL API, you can focus on the development of business logic for LLMs applicationswithout paying attention to cumbersome model and environment details.AWEL adopts a layered API design. AWEL's layered API design architecture is shown in the figure below.AWEL Design&quot;, &quot;meta_info&quot;: &quot;{'source': 'https://docs.dbgpt.site/docs/awel/', 'title': 'AWEL(Agentic Workflow Expression Language) | DB-GPT', 'description': 'Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application', 'language': 'en-US'}&quot;, &quot;recall_score&quot;: 0.6579902643967029}, {&quot;id&quot;: 2531, &quot;content&quot;: &quot;ExamplesThe preliminary version of AWEL has alse been released, and we have provided some built-in usage examples.OperatorsExample of API-RAGYou can find source code from examples/awel/simple_rag_example.py&quot;, &quot;meta_info&quot;: &quot;{'source': 'https://docs.dbgpt.site/docs/awel/', 'title': 'AWEL(Agentic Workflow Expression Language) | DB-GPT', 'description': 'Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application', 'language': 'en-US'}&quot;, &quot;recall_score&quot;: 0.5997033286385491}, {&quot;id&quot;: 2538, &quot;content&quot;: &quot;Stand-alone environmentRay environmentPreviousWhy use AWEL?NextReleased V0.5.0 | Develop native data applications through workflows and agentsAWEL DesignExamplesOperatorsExample of API-RAGAgentFream ExampleDSL ExampleCurrently supported operatorsExecutable environmentCommunityDiscordDockerhubGithubGithubHuggingFaceMoreHacker NewsTwitterCopyright © 2024 DB-GPT&quot;, &quot;meta_info&quot;: &quot;{'source': 'https://docs.dbgpt.site/docs/awel/', 'title': 'AWEL(Agentic Workflow Expression Language) | DB-GPT', 'description': 'Agentic Workflow Expression Language(AWEL) is a set of intelligent agent workflow expression language specially designed for large model application', 'language': 'en-US'}&quot;, &quot;recall_score&quot;: 0.5980204530753225}]}]\" />"}}]}

data: [DONE]
```
### Create Knowledge Space

```python
POST /api/v2/serve/knowledge/spaces
```



<Tabs
  defaultValue="curl_knowledge"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_knowledge'},
    {label: 'Python', value: 'python_knowledge'},
  ]
}>

<TabItem value="curl_knowledge">

```shell
 DBGPT_API_KEY="dbgpt"

 curl --location --request POST 'http://localhost:5670/api/v2/serve/knowledge/spaces' \
--header 'Authorization: Bearer $DBGPT_API_KEY' \
--header 'Content-Type: application/json' \
--data-raw '{"desc": "for client space desc", "name": "test_space_2", "owner": "dbgpt", "vector_type": "Chroma"
}'
```
 </TabItem>

<TabItem value="python_knowledge">

```python
from dbgpt.client import Client
from dbgpt.client.knowledge import create_space
from dbgpt.client.schema import SpaceModel

DBGPT_API_KEY = "dbgpt"

client = Client(api_key=DBGPT_API_KEY)
res = await create_space(client, SpaceModel(
    name="test_space",
    vector_type="Chroma",
    desc="for client space",
    owner="dbgpt"
))
```

 </TabItem>
</Tabs>

#### Request body

________
<b>name</b> <font color="gray"> string </font> <font color="red"> Required </font>

knowledge space name
________
<b>vector_type</b> <font color="gray"> string </font> <font color="red"> Required </font>

vector db type, `Chroma`, `Milvus`, default is `Chroma`
________
<b>desc</b> <font color="gray"> string </font> <font color="red"> Optional </font>

description of the knowledge space
________
<b>owner</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

The owner of the knowledge space
________
<b>context</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

The context of the knowledge space argument
________

#### Response body
Return <a href="#the-space-object">Space Object</a>

### Update Knowledge Space

```python
PUT /api/v2/serve/knowledge/spaces
```

<Tabs
  defaultValue="curl_update_knowledge"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_update_knowledge'},
    {label: 'Python', value: 'python_update_knowledge'},
  ]
}>

<TabItem value="curl_update_knowledge">

```shell
 DBGPT_API_KEY="dbgpt"

 curl --location --request PUT 'http://localhost:5670/api/v2/serve/knowledge/spaces' \
--header 'Authorization: Bearer $DBGPT_API_KEY' \
--header 'Content-Type: application/json' \
--data-raw '{"desc": "for client space desc v2", "id": "49", "name": "test_space_2", "owner": "dbgpt", "vector_type": "Chroma"
}'
```
 </TabItem>

<TabItem value="python_update_knowledge">

```python
from dbgpt.client import Client
from dbgpt.client.knowledge import update_space
from dbgpt.client.schema import SpaceModel

DBGPT_API_KEY = "dbgpt"

client = Client(api_key=DBGPT_API_KEY)
res = await update_space(client, SpaceModel(
    name="test_space",
    vector_type="Chroma",
    desc="for client space update",
    owner="dbgpt"
))

```

 </TabItem>
</Tabs>

#### Request body

________
<b>id</b> <font color="gray"> string </font> <font color="red"> Required </font>

knowledge space id
________
<b>name</b> <font color="gray"> string </font> <font color="red"> Required </font>

knowledge space name
________
<b>vector_type</b> <font color="gray"> string </font> <font color="red"> Optional </font>

vector db type, `Chroma`, `Milvus`, default is `Chroma`
________
<b>desc</b> <font color="gray"> string </font> <font color="red"> Optional </font>

description of the knowledge space
________
<b>owner</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

The owner of the knowledge space
________
<b>context</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

The context of the knowledge space argument
________

#### Response body
Return <a href="#the-space-object">Space Object</a>

### Delete Knowledge Space

```python
DELETE /api/v2/serve/knowledge/spaces
```


<Tabs
  defaultValue="curl_update_knowledge"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_update_knowledge'},
    {label: 'Python', value: 'python_update_knowledge'},
  ]
}>

<TabItem value="curl_update_knowledge">

```shell
 DBGPT_API_KEY=dbgpt
 SPACE_ID={YOUR_SPACE_ID}

 curl -X DELETE "http://localhost:5670/api/v2/serve/knowledge/spaces/$SPACE_ID" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
```
 </TabItem>

<TabItem value="python_update_knowledge">


```python
from dbgpt.client import Client
from dbgpt.client.knowledge import delete_space

DBGPT_API_KEY = "dbgpt"
space_id = "{your_space_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await delete_space(client=client, space_id=space_id)

```

 </TabItem>
</Tabs>

#### Delete Parameters
________
<b>id</b> <font color="gray"> string </font> <font color="red"> Required </font>

knowledge space id
________

#### Response body
Return <a href="#the-space-object">Space Object</a>

### Get Knowledge Space

```python
GET /api/v2/serve/knowledge/spaces/{space_id}
```

<Tabs
  defaultValue="curl_get_knowledge"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_get_knowledge'},
    {label: 'Python', value: 'python_get_knowledge'},
  ]
}>

<TabItem value="curl_get_knowledge">

```shell
DBGPT_API_KEY=dbgpt
SPACE_ID={YOUR_SPACE_ID}
curl -X GET "http://localhost:5670/api/v2/serve/knowledge/spaces/$SPACE_ID" -H "Authorization: Bearer $DBGPT_API_KEY"
```
 </TabItem>

<TabItem value="python_get_knowledge">


```python
from dbgpt.client import Client
from dbgpt.client.knowledge import get_space

DBGPT_API_KEY = "dbgpt"
space_id = "{your_space_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await get_space(client=client, space_id=space_id)

```

 </TabItem>
</Tabs>

#### Query Parameters
________
<b>id</b> <font color="gray"> string </font> <font color="red"> Required </font>

knowledge space id
________

#### Response body
Return <a href="#the-space-object">Space Object</a>

### List Knowledge Space

```python
GET /api/v2/serve/knowledge/spaces
```

<Tabs
  defaultValue="curl_list_knowledge"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_list_knowledge'},
    {label: 'Python', value: 'python_list_knowledge'},
  ]
}>

<TabItem value="curl_list_knowledge">

```shell
 DBGPT_API_KEY=dbgpt

curl -X GET 'http://localhost:5670/api/v2/serve/knowledge/spaces' -H "Authorization: Bearer $DBGPT_API_KEY"
```
 </TabItem>

<TabItem value="python_list_knowledge">


```python
from dbgpt.client import Client
from dbgpt.client.knowledge import list_space

DBGPT_API_KEY = "dbgpt"
space_id = "{your_space_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await list_space(client=client)

```

 </TabItem>
</Tabs>

#### Response body
Return <a href="#the-space-object">Space Object</a> List

### The Space Object

________
<b>id</b> <font color="gray"> string </font>

space id
________
<b>name</b> <font color="gray"> string </font>

knowledge space name
________
<b>vector_type</b> <font color="gray"> string </font> 

vector db type, `Chroma`, `Milvus`, default is `Chroma`
________
<b>desc</b> <font color="gray"> string </font> <font color="red"> Optional </font>

description of the knowledge space
________
<b>owner</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

The owner of the knowledge space
________
<b>context</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

The context of the knowledge space argument
________