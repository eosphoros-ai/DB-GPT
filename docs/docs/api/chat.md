# Chat

Given a list of messages comprising a conversation, the model will return a response.

# Create Chat Completion

```python
POST /api/v2/chat/completions
```

### Examples

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### Stream Chat Completion


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
 DBGPT_API_KEY="dbgpt"

 curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"chatgpt_proxyllm\", \"stream\": true}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt.client import Client

DBGPT_API_KEY = "dbgpt"
client = Client(api_key=DBGPT_API_KEY)

async for data in client.chat_stream(
    model="chatgpt_proxyllm",
    messages="hello",
):
    print(data)
```
 </TabItem>
</Tabs>

### Chat Completion Stream Response
```commandline
data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "Hello"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "!"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " How"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " can"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " I"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " assist"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " you"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": " today"}}]}

data: {"id": "chatcmpl-ba6fb52e-e5b2-11ee-b031-acde48001122", "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "?"}}]}

data: [DONE]
```

### Chat Completion
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
 DBGPT_API_KEY="dbgpt"

 curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"chatgpt_proxyllm\", \"stream\": false}"
```
 </TabItem>

<TabItem value="python">

```python
from dbgpt.client import Client

DBGPT_API_KEY = "dbgpt"
client = Client(api_key=DBGPT_API_KEY)
response = await client.chat(model="chatgpt_proxyllm" ,messages="hello")
```
 </TabItem>
</Tabs>

### Chat Completion Response
```json
{
    "id": "a8321543-52e9-47a5-a0b6-3d997463f6a3",
    "object": "chat.completion",
    "created": 1710826792,
    "model": "chatgpt_proxyllm",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello! How can I assist you today?"
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



### Request body
________
<b>messages</b> <font color="gray"> string </font> <font color="red"> Required </font>

A list of messages comprising the conversation so far. Example Python code.
________
<b>model</b> <font color="gray"> string </font> <font color="red"> Required </font>

ID of the model to use. See the model endpoint compatibility table for details on which models work with the Chat API.
________
<b>chat_mode</b> <font color="gray"> string </font> <font color="red"> Optional </font>

The DB-GPT chat mode, which can be one of the following: `chat_normal`, `chat_app`, `chat_knowledge`, `chat_flow`, default is `chat_normal`.
________
<b>chat_param</b> <font color="gray"> string </font> <font color="red"> Optional </font>

The DB-GPT The chat param value of chat mode: `{app_id}`, `{space_id}`, `{flow_id}`, default is `None`.
________
<b>max_new_tokens</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

The maximum number of tokens that can be generated in the chat completion.

The total length of input tokens and generated tokens is limited by the model's context length.
________
<b>stream</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

If set, partial message deltas will be sent. 
Tokens will be sent as data-only server-sent events as they become available, with the stream terminated by a `data: [DONE]`
________
<b>temperature</b> <font color="gray"> integer </font> <font color="red"> Optional </font>

What sampling temperature to use, between 0 and 2. Higher values like 0.8 will make the output more random, while lower values like 0.2 will make it more focused and deterministic.
________
<b>conv_uid</b> <font color="gray"> string </font> <font color="red"> Optional </font>

The conversation id of the model inference, default is `None`
________
<b>span_id</b> <font color="gray"> string </font> <font color="red"> Optional </font>

The span id of the model inference, default is `None`
________
<b>sys_code</b> <font color="gray"> string </font> <font color="red"> Optional </font>

The system code, default is `None`
________
<b>user_name</b> <font color="gray"> string </font> <font color="red"> Optional </font>

The web server user name, default is `None`
________


### Chat Stream Response Body
________
<b>id</b> <font color="gray"> string </font>

conv_uid of the convsersation.
________
<b>model</b> <font color="gray"> string </font>

The model used for the chat completion.

________
<b>created</b> <font color="gray"> string </font>

The Unix timestamp (in seconds) of when the chat completion was created.
________
<b>choices</b> <font color="gray"> array </font>

A list of chat completion choices. Can be more than one if n is greater than 1.

  - <b>index</b> <font color="gray"> integer </font>

    The index of the choice in the list of choices.
  - <b>delta</b> <font color="gray"> object </font>

    The chat completion delta.
    - <b>role</b> <font color="gray"> string </font>

      The role of the speaker. Can be `user` or `assistant`.
    - <b>content</b> <font color="gray"> string </font>

      The content of the message.
    - <b>finish_reason</b> <font color="gray"> string </font>
    
        The reason the chat completion finished. Can be `max_tokens` or `stop`.
________


### Chat Response Body
________
<b>id</b> <font color="gray"> string </font>

conv_uid of the convsersation.
________
<b>model</b> <font color="gray"> string </font>

The model used for the chat completion.

________
<b>created</b> <font color="gray"> string </font>

The Unix timestamp (in seconds) of when the chat completion was created.
________
<b>object</b> <font color="gray"> string </font>

The object type of the chat completion.
________
<b>choices</b> <font color="gray"> array </font>

A list of chat completion choices. Can be more than one if n is greater than 1.

  - <b>index</b> <font color="gray"> integer </font>

    The index of the choice in the list of choices.

  - <b>delta</b> <font color="gray"> object </font>

    The chat completion delta.
    - <b>role</b> <font color="gray"> string </font>

      The role of the speaker. Can be `user` or `assistant`.
    - <b>content</b> <font color="gray"> string </font>

      The content of the message.
    - <b>finish_reason</b> <font color="gray"> string </font>
    
        The reason the chat completion finished. Can be `max_tokens` or `stop`.
________
<b>usage</b> <font color="gray"> object </font>

    The usage statistics for the chat completion.
    - <b>prompt_tokens</b> <font color="gray"> integer </font>

      The number of tokens in the prompt.
    - <b>total_tokens</b> <font color="gray"> integer </font>

      The total number of tokens in the chat completion.
    - <b>completion_tokens</b> <font color="gray"> integer </font>

      The number of tokens in the chat completion.


