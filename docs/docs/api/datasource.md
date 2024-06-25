# Datasource

Get started with the Datasource API

# Chat Datasource

```python
POST /api/v2/chat/completions
```
### Examples

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

### Chat Datasource


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
DB_NAME="{your_db_name}"

curl -X POST "http://localhost:5670/api/v2/chat/completions" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"messages\":\"show space datas limit 5\",\"model\":\"chatgpt_proxyllm\", \"chat_mode\": \"chat_data\", \"chat_param\": \"$DB_NAME\"}"

```
 </TabItem>

<TabItem value="python">

```python
from dbgpt.client import Client

DBGPT_API_KEY = "dbgpt"
DB_NAME="{your_db_name}"

client = Client(api_key=DBGPT_API_KEY)
res = client.chat(
    messages="show space datas limit 5", 
    model="chatgpt_proxyllm", 
    chat_mode="chat_data", 
    chat_param=DB_NAME
)
```
 </TabItem>
</Tabs>

#### Chat Completion Response
```json
{
    "id": "2bb80fdd-e47e-4083-8bc9-7ca66ee0931b",
    "object": "chat.completion",
    "created": 1711509733,
    "model": "chatgpt_proxyllm",
    "choices": [
        {
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "The user wants to display information about knowledge spaces with a limit of 5 results.\\n<chart-view content=\"{\"type\": \"response_table\", \"sql\": \"SELECT * FROM knowledge_space LIMIT 5\", \"data\": [{\"id\": 5, \"name\": \"frfrw\", \"vector_type\": \"Chroma\", \"desc\": \"eee\", \"owner\": \"eee\", \"context\": null, \"gmt_created\": \"2024-01-02T13:29:52\", \"gmt_modified\": \"2024-01-02T13:29:52\", \"description\": null}, {\"id\": 7, \"name\": \"acc\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T13:47:01\", \"gmt_modified\": \"2024-01-02T13:47:01\", \"description\": null}, {\"id\": 8, \"name\": \"bcc\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T14:22:02\", \"gmt_modified\": \"2024-01-02T14:22:02\", \"description\": null}, {\"id\": 9, \"name\": \"dede\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T14:36:18\", \"gmt_modified\": \"2024-01-02T14:36:18\", \"description\": null}, {\"id\": 10, \"name\": \"qqq\", \"vector_type\": \"Chroma\", \"desc\": \"dede\", \"owner\": \"dede\", \"context\": null, \"gmt_created\": \"2024-01-02T14:40:56\", \"gmt_modified\": \"2024-01-02T14:40:56\", \"description\": null}]}\" />"
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
### Create Datasource

```python
POST /api/v2/serve/datasources
```
#### Request body
Request <a href="#the-flow-object">Datasource Object</a>

#### Response body
Return <a href="#the-flow-object">Datasource Object</a>


### Update Datasource
```python
PUT /api/v2/serve/datasources
```

#### Request body
Request <a href="#the-flow-object">Datasource Object</a>

#### Response body
Return <a href="#the-flow-object">Datasource Object</a>

### Delete Datasource

```python
DELETE /api/v2/serve/datasources
```

<Tabs
  defaultValue="curl_update_datasource"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_update_datasource'},
    {label: 'Python', value: 'python_update_datasource'},
  ]
}>

<TabItem value="curl_update_datasource">

```shell
DBGPT_API_KEY=dbgpt
DATASOURCE_ID={YOUR_DATASOURCE_ID}
 
 curl -X DELETE "http://localhost:5670/api/v2/serve/datasources/$DATASOURCE_ID" \
    -H "Authorization: Bearer $DBGPT_API_KEY" \

```
 </TabItem>

<TabItem value="python_update_datasource">


```python
from dbgpt.client import Client
from dbgpt.client.datasource import delete_datasource

DBGPT_API_KEY = "dbgpt"
datasource_id = "{your_datasource_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await delete_datasource(client=client, datasource_id=datasource_id)

```

 </TabItem>
</Tabs>

#### Delete Parameters
________
<b>datasource_id</b> <font color="gray"> string </font> <font color="red"> Required </font>

datasource id
________

#### Response body
Return <a href="#the-flow-object">Datasource Object</a>

### Get Datasource

```python
GET /api/v2/serve/datasources/{datasource_id}
```
<Tabs
  defaultValue="curl_get_datasource"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_get_datasource'},
    {label: 'Python', value: 'python_get_datasource'},
  ]
}>

<TabItem value="curl_get_datasource">

```shell
DBGPT_API_KEY=dbgpt
DATASOURCE_ID={YOUR_DATASOURCE_ID}

curl -X GET "http://localhost:5670/api/v2/serve/datasources/$DATASOURCE_ID" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_get_datasource">


```python
from dbgpt.client import Client
from dbgpt.client.datasource import get_datasource

DBGPT_API_KEY = "dbgpt"
datasource_id = "{your_datasource_id}"

client = Client(api_key=DBGPT_API_KEY)
res = await get_datasource(client=client, datasource_id=datasource_id)

```

 </TabItem>
</Tabs>

#### Query Parameters
________
<b>datasource_id</b> <font color="gray"> string </font> <font color="red"> Required </font>

datasource id
________

#### Response body
Return <a href="#the-flow-object">Datasource Object</a>

### List Datasource

```python
GET /api/v2/serve/datasources
```


<Tabs
  defaultValue="curl_list_datasource"
  groupId="chat1"
  values={[
    {label: 'Curl', value: 'curl_list_datasource'},
    {label: 'Python', value: 'python_list_datasource'},
  ]
}>

<TabItem value="curl_list_datasource">

```shell
DBGPT_API_KEY=dbgpt

curl -X GET "http://localhost:5670/api/v2/serve/datasources" -H "Authorization: Bearer $DBGPT_API_KEY"

```
 </TabItem>

<TabItem value="python_list_datasource">


```python
from dbgpt.client import Client
from dbgpt.client.datasource import list_datasource

DBGPT_API_KEY = "dbgpt"

client = Client(api_key=DBGPT_API_KEY)
res = await list_datasource(client=client)

```

 </TabItem>
</Tabs>

#### Response body
Return <a href="#the-flow-object">Datasource Object</a>

### The Datasource Object

________
<b>id</b> <font color="gray">string</font>

The unique id for the datasource.
________
<b>db_name</b> <font color="gray">string</font>

The Database name
________
<b>db_type</b> <font color="gray">string</font>

Database type, e.g. sqlite, mysql, etc.
________
<b>db_path</b> <font color="gray">string</font>

File path for file-based database.
________
<b>db_host</b> <font color="gray">string</font>

Database host.
________
<b>db_port</b> <font color="gray">object</font>

Database port.
________
<b>db_user</b> <font color="gray">string</font>

Database user.
________
<b>db_pwd</b> <font color="gray">string</font>

Database password.
________
<b>comment</b> <font color="gray">string</font>

Comment for the database.
________
