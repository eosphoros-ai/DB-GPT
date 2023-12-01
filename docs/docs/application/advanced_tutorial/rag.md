# RAG Parameter Adjustment
Each knowledge space supports argument customization, including the relevant arguments for vector retrieval and the arguments for knowledge question-answering prompts.
####  Embedding Arguments
Embedding Argument
![upload](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/f1221bd5-d049-4ceb-96e6-8709e76e502e)

:::tip Embedding Arguments
* topk:the top k vectors based on similarity score.
* recall_score:set a similarity threshold score for the retrieval of similar vectors.
* recall_type:recall type. 
* model:A model used to create vector representations of text or other data.
* chunk_size:The size of the data chunks used in processing.
* chunk_overlap:The amount of overlap between adjacent data chunks.
:::

#### Prompt Arguments
Prompt Argument
![upload](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/9918c9c3-ed64-4804-9e05-fa7d7d177bec)

:::tip Prompt Arguments
* scene:A contextual parameter used to define the setting or environment in which the prompt is being used.
* template:A pre-defined structure or format for the prompt, which can help ensure that the AI system generates responses that are consistent with the desired style or tone.
* max_token:The maximum number of tokens or words allowed in a prompt. 
:::

#### Summary Arguments
Summary Argument
![image](https://github.com/eosphoros-ai/DB-GPT/assets/13723926/96782ba2-e9a2-4173-a003-49d44bf874cc)

:::tip summary arguments
* max_iteration: summary max iteration call with llm, default 5.
* concurrency_limit: default summary concurrency call with llm, default 3.
:::

#### Knowledge Query Rewrite
set ``KNOWLEDGE_SEARCH_REWRITE=True`` in ``.env`` file, and restart the server.

```shell
# Whether to enable Chat Knowledge Search Rewrite Mode
KNOWLEDGE_SEARCH_REWRITE=False
```

#### Change Vector Database

set ``VECTOR_STORE_TYPE`` in ``.env`` file, and restart the server.

```shell
### Chroma vector db config
VECTOR_STORE_TYPE=Chroma
#CHROMA_PERSIST_PATH=/root/DB-GPT/pilot/data

### Milvus vector db config
#VECTOR_STORE_TYPE=Milvus
#MILVUS_URL=127.0.0.1
#MILVUS_PORT=19530
#MILVUS_USERNAME
#MILVUS_PASSWORD
#MILVUS_SECURE=

### Weaviate vector db config
#VECTOR_STORE_TYPE=Weaviate
#WEAVIATE_URL=https://kt-region-m8hcy0wc.weaviate.network

