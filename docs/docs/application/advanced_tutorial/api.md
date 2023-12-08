# API Interface Usage

The DB-GPT project currently also provides various APIs for use. Currently APIs are mainly divided into two categories. 1. Model API 2. Application service layer AP

Model API mainly means that DB-GPT adapts to various models and is uniformly packaged into models compatible with OpenAI SDK output. The service layer API refers to the API exposed by the DB-GPT service layer. The following is a brief introduction to the use of both.

## Model API

In the DB-GPT project, we defined a service-oriented multi-model management framework (SMMF). Through the capabilities of SMMF, we can deploy multiple models, and these models provide external services through services. In order to allow clients to achieve seamless switching, we uniformly support the OpenAI SDK standards.
- Detail useage tutorial: [OpenAI SDK calls local multi-model ](/docs/installation/advanced_usage/OpenAI_SDK_call.md)

**Example:** The following is an example of calling through openai sdk

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


## Application service layer API
The service layer API refers to the API exposed on port 5000 after starting the webserver, which is mainly focused on the application layer. It can be divided into the following parts according to categories

- Chat API
- Editor API
- LLM Manage API
- Agent API
- AWEL API
- Model API

:::info
Note: After starting the webserver, open http://127.0.0.1:5000/docs to view details

Regarding the service layer API, in terms of strategy in the early days, we maintained the principle of minimum availability and openness. APIs that are stably exposed to the outside world will carry version information, such as
- /api/v1/
- /api/v2/

Due to the rapid development of the entire field, different versions of the API will not be considered fully compatible in terms of compatibility. In subsequent new versions of the API, we will provide instructions in the documentation for incompatible APIs.
:::

## API Description 

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="chatapi"
  values={[
    {label: 'Chat API', value: 'chatapi'},
    {label: 'Editor API', value: 'editorapi'},
    {label: 'Model API', value: 'modelapi'},
    {label: 'LLM Manage API', value: 'llmanageapi'},
    {label: 'Agent API', value: 'agentapi'},
    {label: 'AWEL API', value: 'awelapi'},
  ]}>
  <TabItem value="chatapi">    

  Chat API Lists

  ```python
    api/v1/chat/db/list
    api/v1/chat/db/add
    api/v1/chat/db/edit
    api/v1/chat/db/delete
    api/v1/chat/db/test/connect
    api/v1/chat/db/summary
    api/v1/chat/db/support/type
    api/v1/chat/dialogue/list
    api/v1/chat/dialogue/scenes
    api/v1/chat/dialogue/new
    api/v1/chat/mode/params/list
    api/v1/chat/mode/params/file/load
    api/v1/chat/dialogue/delete
    api/v1/chat/dialogue/messages
    api/v1/chat/prepare
    api/v1/chat/completions
  ```
  </TabItem>
  <TabItem value="editorapi">   

  Editor API Lists
  
  ```python
    api/v1/editor/db/tables
    api/v1/editor/sql/rounds
    api/v1/editor/sql
    api/v1/editor/sql/run
    api/v1/sql/editor/submit
    api/v1/editor/chart/list
    api/v1/editor/chart/info
    api/v1/editor/chart/run
    api/v1/chart/editor/submit
  ```
  </TabItem>
  <TabItem value="modelapi">   
    
  Model API Lists

  ```python
    api/v1/model/types
    api/v1/model/supports
  ```
  </TabItem>
  <TabItem value="llmanageapi">   
    
  LLM Manage API Lists

  ```python
    api/v1/worker/model/params
    api/v1/worker/model/list
    api/v1/worker/model/stop
    api/v1/worker/model/start
    api/worker/generate_stream
    api/worker/generate
    api/worker/embeddings
    api/worker/apply
    api/worker/parameter/descriptions
    api/worker/models/supports
    api/worker/models/startup
    api/worker/models/shutdown
    api/controller/models
    api/controller/heartbeat
  ```
  </TabItem>
  <TabItem value="agentapi">   
    
  Agent API Lists

  ```python
    api/v1/agent/hub/update
    api/v1/agent/query
    api/v1/agent/my
    api/v1/agent/install
    api/v1/agent/uninstall
    api/v1/personal/agent/upload
  ```
  </TabItem>
  <TabItem value="awelapi">   
    
  AWEL API Lists

  ```python
    api/v1/awel/trigger/examples/simple_rag
    api/v1/awel/trigger/examples/simple_chat
    api/v1/awel/trigger/examples/hello
  ```

  </TabItem>
</Tabs>

:::info note

⚠️  Knowledge and Prompt API

Currently, due to frequent changes in Knowledge and Prompt, the relevant APIs are still in the testing stage and will be gradually opened later

:::

More detailed interface parameters can be viewed at `http://127.0.0.1:5000/docs`

