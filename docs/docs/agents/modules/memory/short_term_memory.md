# Short-term Memory

Short-term memory temporarily buffers recent perceptions, it will receive  some of the 
sensory memory, and it can be **enhanced** by other observations or retrieved memories to 
enter the long-term memory.

In most cases, short-term memory is analogous to the input information within the context
window constrained by the LLM.
So you can think of short-term memory will be written into the prompt of the LLM in most cases.

## Using Short-term Memory

```python
from dbgpt.agent import AgentMemory, ShortTermMemory

# Create an agent memory, which contains a short-term memory
memory = ShortTermMemory(buffer_size=2)
agent_memory: AgentMemory = AgentMemory(memory=memory)
```

Like sensory memory, short-term memory is also has a buffer size, when the buffer is full,
it will keep the latest buffer_size memories, and some of the discarded memories will 
be transferred to long-term memory.

The default short-term memory is a `FIFO` buffered memory, we won't introduce too much here.

## Enhanced Short-term Memory

Like human short-term memory, the short-term memory in DB-GPT agents can be enhanced by outside observations.
Here we introduce a kind of enhanced short-term memory, which is called `EnhancedShortTermMemory`, 
it enhances memories by comparing the similarity between the new observation and the existing memories.

To use `EnhancedShortTermMemory`, you need to provide a embeddings model.

### Prepare Embedding Model

DB-GPT supports 
a lot of embedding models, here are some of them:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI(API)', value: 'openai'},
    {label: 'text2vec(local)', value: 'text2vec'},
    {label: 'Embedding API Server(cluster)', value: 'remote_embedding'},
  ]}>

  <TabItem value="openai">

```python
import os
from dbgpt.rag.embedding import DefaultEmbeddingFactory

api_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/embeddings"
api_key = os.getenv("OPENAI_API_KEY")
embeddings = DefaultEmbeddingFactory.openai(api_url=api_url, api_key=api_key)
```
  </TabItem>

  <TabItem value="text2vec">

```python
from dbgpt.rag.embedding import DefaultEmbeddingFactory

embeddings = DefaultEmbeddingFactory.default("/data/models/text2vec-large-chinese")
```
</TabItem>

<TabItem value="remote_embedding">

If you have deployed [DB-GPT cluster](../../../installation/model_service/cluster) and 
[API server](../../../installation/advanced_usage/OpenAI_SDK_call)
, you can connect to the API server to get the embeddings.

```python
from dbgpt.rag.embedding import DefaultEmbeddingFactory

embeddings = DefaultEmbeddingFactory.remote(
  api_url="http://localhost:8100/api/v1/embeddings",
  api_key="{your_api_key}",
  model_name="text2vec"
)
```

</TabItem>
</Tabs>

### Using Enhanced Short-term Memory

```python
from concurrent.futures import ThreadPoolExecutor
from dbgpt.agent import AgentMemory, EnhancedShortTermMemory

# Create an agent memory, which contains a short-term memory
memory = EnhancedShortTermMemory(
    embeddings=embeddings,
    buffer_size=2,
    enhance_similarity_threshold=0.5,
    enhance_threshold=3,
    executor=ThreadPoolExecutor(),
)
agent_memory: AgentMemory = AgentMemory(memory=memory)
```
In DB-GPT, the core interface is asynchronous and non-blocking, so we use `ThreadPoolExecutor` to 
run the similarity calculation in a separate thread for better performance.

In the above code, we set the `enhance_similarity_threshold` to `0.5`, which means if the 
similarity bigger than `0.7`, the new observation has the probability of being enhanced to the
short-term memory(there are a random factor in the enhancement process).
And we set the `enhance_threshold` to `3`, which means if the memory is enhanced bigger or equal to `3` times, 
it will be transferred to long-term memory.

Then you can use the enhanced short-term memory in your agent.

