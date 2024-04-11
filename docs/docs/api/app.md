# App

Get started with the App API

# Chat App

```python
POST /api/v2/chat/completions
```
### Examples

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### Stream Chat App


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
 APP_ID={YOUR_APP_ID}

 curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"chatgpt_proxyllm\", \"chat_mode\": \"chat_app\", \"chat_param\": \"$APP_ID\"}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt.client import Client

DBGPT_API_KEY = "dbgpt"
APP_ID="{YOUR_APP_ID}"

client = Client(api_key=DBGPT_API_KEY)

async for data in client.chat_stream(
    messages="Introduce AWEL", 
    model="chatgpt_proxyllm", 
    chat_mode="chat_app", 
    chat_param=APP_ID
):
    print(data)

```
 </TabItem>
</Tabs>

### Chat Completion Stream Response
```commandline
data: {"id": "109bfc28-fe87-452c-8e1f-d4fe43283b7d", "created": 1710919480, "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "```agent-plans\n[{\"name\": \"Introduce Awel\", \"num\": 2, \"status\": \"complete\", \"agent\": \"Human\", \"markdown\": \"```agent-messages\\n[{\\\"sender\\\": \\\"Summarizer\\\", \\\"receiver\\\": \\\"Human\\\", \\\"model\\\": \\\"chatgpt_proxyllm\\\", \\\"markdown\\\": \\\"Agentic Workflow Expression Language (AWEL) is a specialized language designed for developing large model applications with intelligent agent workflows. It offers flexibility and functionality, allowing developers to focus on business logic for LLMs applications without getting bogged down in model and environment details. AWEL uses a layered API design architecture, making it easier to work with. You can find examples and source code to get started with AWEL, and it supports various operators and environments. AWEL is a powerful tool for building native data applications through workflows and agents.\"}]\n```"}}]}

data: [DONE]
```
### Get App

```python
GET /api/v2/serve/apps/{app_id}
```

<Tabs
  defaultValue="curl_get_app"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_get_app'},
    {label: 'Python', value: 'python_get_app'},
  ]
}>

<TabItem value="curl_get_app">

```shell
DBGPT_API_KEY=dbgpt
APP_ID={YOUR_APP_ID}
curl -X GET "http://localhost:5670/api/v2/serve/apps/$APP_ID" -H "Authorization: Bearer $DBGPT_API_KEY"
```
 </TabItem>

<TabItem value="python_get_app">


```python
from dbgpt.client import Client
from dbgpt.client.app import get_app

DBGPT_API_KEY = "dbgpt"
app_id = "{your_app_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await get_app(client=client, app_id=app_id)

```

 </TabItem>
</Tabs>


#### Query Parameters
________
<b>app_id</b> <font color="gray"> string </font> <font color="red"> Required </font>

app id
________

#### Response body
Return <a href="#the-app-object">App Object</a>

### List App

```python
GET /api/v2/serve/apps
```
<Tabs
  defaultValue="curl_list_app"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_list_app'},
    {label: 'Python', value: 'python_list_app'},
  ]
}>

<TabItem value="curl_list_app">

```shell
DBGPT_API_KEY=dbgpt

curl -X GET 'http://localhost:5670/api/v2/serve/apps' -H "Authorization: Bearer $DBGPT_API_KEY"
```
 </TabItem>

<TabItem value="python_list_app">


```python
from dbgpt.client import Client
from dbgpt.client.app import list_app

DBGPT_API_KEY = "dbgpt"
app_id = "{your_app_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await list_app(client=client)

```

 </TabItem>
</Tabs>

#### Response body
Return <a href="#the-app-object">App Object</a> List

### The App Model
________
<b>app_code</b> <font color="gray"> string </font>

unique app id
________
<b>app_name</b> <font color="gray"> string </font>

app name
________

<b>app_describe</b> <font color="gray"> string </font>

app describe
________
<b>team_mode</b> <font color="gray"> string </font>

team mode
________
<b>language</b> <font color="gray"> string </font>

language
________
<b>team_context</b> <font color="gray"> string </font>

team context
________
<b>user_code</b> <font color="gray"> string </font>

user code
________
<b>sys_code</b> <font color="gray"> string </font>

sys code
________
<b>is_collected</b> <font color="gray"> string </font>

is collected
________
<b>icon</b> <font color="gray"> string </font>

icon
________
<b>created_at</b> <font color="gray"> string </font>

created at
________
<b>updated_at</b> <font color="gray"> string </font>

updated at
________
<b>details</b> <font color="gray"> string </font>

app details List[AppDetailModel]
________

### The App Detail Model
________
<b>app_code</b> <font color="gray"> string </font>

app code
________
<b>app_name</b> <font color="gray"> string </font>

app name
________
<b>agent_name</b> <font color="gray"> string </font>

agent name
________
<b>node_id</b> <font color="gray"> string </font>

node id
________
<b>resources</b> <font color="gray"> string </font>

resources
________
<b>prompt_template</b> <font color="gray"> string </font>

prompt template
________
<b>llm_strategy</b> <font color="gray"> string </font>

llm strategy
________
<b>llm_strategy_value</b> <font color="gray"> string </font>

llm strategy value
________
<b>created_at</b> <font color="gray"> string </font>

created at
________
<b>updated_at</b> <font color="gray"> string </font>

updated at
________
