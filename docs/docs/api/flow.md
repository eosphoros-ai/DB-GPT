# Flow

Get started with the App API

# Chat Flow

```python
POST /api/v2/chat/completions
```
### Examples

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### Stream Chat Flow


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
FLOW_ID={YOUR_FLOW_ID}

curl -X POST "http://localhost:5000/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"Hello\",\"model\":\"chatgpt_proxyllm\", \"chat_mode\": \"chat_flow\", \"chat_param\": \"$FLOW_ID\"}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt.client import Client

DBGPT_API_KEY = "dbgpt"
FLOW_ID="{YOUR_FLOW_ID}"

client = Client(api_key=DBGPT_API_KEY)
async for data in client.chat_stream(
    messages="Introduce AWEL", 
    model="chatgpt_proxyllm", 
    chat_mode="chat_flow", 
    chat_param=FLOW_ID
):
    print(data)
```
 </TabItem>
</Tabs>

#### Chat Completion Stream Response
```commandline
data: {"id": "579f8862-fc4b-481e-af02-a127e6d036c8", "created": 1710918094, "model": "chatgpt_proxyllm", "choices": [{"index": 0, "delta": {"role": "assistant", "content": "\n\n"}}]}
```
### Create Flow

```python
POST /api/v2/serve/awel/flows
```
#### Request body
Request <a href="#the-flow-object">Flow Object</a>

#### Response body
Return <a href="#the-flow-object">Flow Object</a>


### Update Flow

PUT /api/v2/serve/awel/flows

#### Request body
Request <a href="#the-flow-object">Flow Object</a>

#### Response body
Return <a href="#the-flow-object">Flow Object</a>

### Delete Flow

```python
DELETE /api/v2/serve/awel/flows
```

<Tabs
  defaultValue="curl_update_flow"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_update_flow'},
    {label: 'Python', value: 'python_update_flow'},
  ]
}>

<TabItem value="curl_update_flow">

```shell
DBGPT_API_KEY=dbgpt
FLOW_ID={YOUR_FLOW_ID}
 
 curl -X DELETE "http://localhost:5000/api/v2/serve/awel/flows/$FLOW_ID" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \

```
 </TabItem>

<TabItem value="python_update_flow">


```python
from dbgpt.client import Client
from dbgpt.client.flow import delete_flow

DBGPT_API_KEY = "dbgpt"
flow_id = "{your_flow_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await delete_flow(client=client, flow_id=flow_id)

```

 </TabItem>
</Tabs>

#### Delete Parameters
________
<b>uid</b> <font color="gray"> string </font> <font color="red"> Required </font>

flow id
________

#### Response body
Return <a href="#the-flow-object">Flow Object</a>

### Get Flow

```python
GET /api/v2/serve/awel/flows/{flow_id}
```
<Tabs
  defaultValue="curl_get_flow"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_get_flow'},
    {label: 'Python', value: 'python_get_flow'},
  ]
}>

<TabItem value="curl_get_flow">

```shell
DBGPT_API_KEY=dbgpt
FLOW_ID={YOUR_FLOW_ID}

curl -X GET "http://localhost:5000/api/v2/serve/awel/flows/$FLOW_ID" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_get_flow">


```python
from dbgpt.client import Client
from dbgpt.client.knowledge import get_flow

DBGPT_API_KEY = "dbgpt"
flow_id = "{your_flow_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await get_flow(client=client, flow_id=flow_id)

```

 </TabItem>
</Tabs>

#### Query Parameters
________
<b>uid</b> <font color="gray"> string </font> <font color="red"> Required </font>

flow id
________

#### Response body
Return <a href="#the-flow-object">Flow Object</a>

### List Flow

```python
GET /api/v2/serve/awel/flows
```


<Tabs
  defaultValue="curl_list_flow"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_list_flow'},
    {label: 'Python', value: 'python_list_flow'},
  ]
}>

<TabItem value="curl_list_flow">

```shell
DBGPT_API_KEY=dbgpt

curl -X GET "http://localhost:5000/api/v2/serve/awel/flows" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_list_flow">


```python
from dbgpt.client import Client
from dbgpt.client.flow import list_flow

DBGPT_API_KEY = "dbgpt"

client = Client(api_key=DBGPT_API_KEY)
res = await list_flow(client=client)

```

 </TabItem>
</Tabs>

#### Response body
Return <a href="#the-flow-object">Flow Object</a>

### The Flow Object

________
<b>uid</b> <font color="gray">string</font>

The unique id for the flow.
________
<b>name</b> <font color="gray">string</font>

The name of the flow.
________
<b>description</b> <font color="gray">string</font>

The description of the flow.
________
<b>label</b> <font color="gray">string</font>

The label of the flow.
________
<b>flow_category</b> <font color="gray">string</font>

The category of the flow. Default is FlowCategory.COMMON.
________
<b>flow_data</b> <font color="gray">object</font>

The flow data.
________
<b>state</b> <font color="gray">string</font>

The state of the flow.Default is INITIALIZING.
________
<b>error_message</b> <font color="gray">string</font>

The error message of the flow.
________
<b>source</b> <font color="gray">string</font>

The source of the flow. Default is DBGPT-WEB.
________
<b>source_url</b> <font color="gray">string</font>

The source url of the flow.
________
<b>version</b> <font color="gray">string</font>

The version of the flow. Default is 0.1.0.
________
<b>editable</b> <font color="gray">boolean</font>

Whether the flow is editable. Default is True.
________
<b>user_name</b> <font color="gray">string</font>

The user name of the flow.
________
<b>sys_code</b> <font color="gray">string</font>

The system code of the flow.
________
<b>dag_id</b> <font color="gray">string</font>

The dag id of the flow.
________
<b>gmt_created</b> <font color="gray">string</font>

The created time of the flow.
________
<b>gmt_modified</b> <font color="gray">string</font>

The modified time of the flow.
________