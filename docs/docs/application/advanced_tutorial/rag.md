# RAG Parameter Adjustment
Each knowledge space supports argument customization, including the relevant arguments for vector retrieval and the arguments for knowledge question-answering prompts.

As shown in the figure below, clicking on the "Knowledge" will trigger a pop-up dialog box. Click the "Arguments" button to enter the parameter tuning interface.
![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/f02039ea-01d7-493a-acd9-027020d54267)


<Tabs
  defaultValue="Embedding"
  values={[
    {label: 'Embedding Argument', value: 'Embedding'},
    {label: 'Prompt Argument', value: 'Prompt'},
    {label: 'Summary Argument', value: 'Summary'},
  ]}>
  <TabItem value="Embedding" label="Embedding Argument">

![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/8a69aba0-3b28-449d-8fd8-ce5bf8dbf7fc)

:::tip Embedding Arguments
* topk:the top k vectors based on similarity score.
* recall_score:set a similarity threshold score for the retrieval of similar vectors. between 0 and 1. default 0.3.
* recall_type:recall type. now nly support topk by vector similarity.
* model:A model used to create vector representations of text or other data.
* chunk_size:The size of the data chunks used in processing.default 500.
* chunk_overlap:The amount of overlap between adjacent data chunks.default 50.
:::
 </TabItem>

<TabItem value="Prompt" label="Prompt Argument">

![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/00f12903-8d70-4bfb-9f58-26f03a6a4773)

:::tip Prompt Arguments
* scene:A contextual parameter used to define the setting or environment in which the prompt is being used.
* template:A pre-defined structure or format for the prompt, which can help ensure that the AI system generates responses that are consistent with the desired style or tone.
* max_token:The maximum number of tokens or words allowed in a prompt. 
:::

 </TabItem>

<TabItem value="Summary" label="Summary Argument">

![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/96782ba2-e9a2-4173-a003-49d44bf874cc)

:::tip summary arguments
* max_iteration: summary max iteration call with llm, default 5. the bigger and better for document summary but time will cost longer.
* concurrency_limit: default summary concurrency call with llm, default 3.
:::

 </TabItem>

</Tabs>

# Knowledge Query Rewrite
set ``KNOWLEDGE_SEARCH_REWRITE=True`` in ``.env`` file, and restart the server.

```shell
# Whether to enable Chat Knowledge Search Rewrite Mode
KNOWLEDGE_SEARCH_REWRITE=True
```

# Change Vector Database
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="Chroma"
  values={[
    {label: 'Chroma', value: 'Chroma'},
    {label: 'Milvus', value: 'Milvus'},
    {label: 'Weaviate', value: 'Weaviate'},
    {label: 'OceanBase', value: 'OceanBase'},
  ]}>
  <TabItem value="Chroma" label="Chroma">

set ``VECTOR_STORE_TYPE`` in ``.env`` file.

```shell
### Chroma vector db config
VECTOR_STORE_TYPE=Chroma
#CHROMA_PERSIST_PATH=/root/DB-GPT/pilot/data
```
 </TabItem>

<TabItem value="Milvus" label="Milvus">
    

set ``VECTOR_STORE_TYPE`` in ``.env`` file

```shell
### Milvus vector db config
VECTOR_STORE_TYPE=Milvus
MILVUS_URL=127.0.0.1
MILVUS_PORT=19530
#MILVUS_USERNAME
#MILVUS_PASSWORD
#MILVUS_SECURE=
  ```
 </TabItem>

<TabItem value="Weaviate" label="Weaviate">

set ``VECTOR_STORE_TYPE`` in ``.env`` file

```shell
### Weaviate vector db config
VECTOR_STORE_TYPE=Weaviate
#WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network
 ```
 </TabItem>

<TabItem value="OceanBase" label="OceanBase">

set ``VECTOR_STORE_TYPE`` in ``.env`` file

```shell
OB_HOST=127.0.0.1
OB_PORT=2881
OB_USER=root@test
OB_DATABASE=test
## Optional
# OB_PASSWORD=
## Optional: If {OB_ENABLE_NORMALIZE_VECTOR} is set, the vector stored in OceanBase is normalized.
# OB_ENABLE_NORMALIZE_VECTOR=True
```
 </TabItem>
</Tabs>
