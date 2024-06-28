# Hybrid Memory

> This structure explicitly models the human short-term and long-term memories. The 
> short-term memory temporarily buffers recent perceptions, while long-term memory consolidates 
> important information over time.


For example, the short-term memory contains the context information about the agent current situations, 
while the long-term memory stores the agent past behaviors and thoughts, which can be retrieved according to the current events.

## Creating A Hybrid Memory

### Method 1: Creating A Hybrid Memory with Default Values

It will use OpenAI Embedding API and ChromaStore as the default values.

```python
import shutil
from dbgpt.agent import HybridMemory, AgentMemory

# Delete old vector store directory(/tmp/tmp_ltm_vector_stor)
shutil.rmtree("/tmp/tmp_ltm_vector_store", ignore_errors=True)
hybrid_memory = HybridMemory.from_chroma(
    vstore_name="agent_memory", vstore_path="/tmp/tmp_ltm_vector_store"
)

agent_memory: AgentMemory = AgentMemory(memory=hybrid_memory)
```

### Method 2: Creating A Hybrid Memory With Custom Values

The hybrid memory requires sensory memory, short-term memory, and long-term memory to be created.

**Prepare Embedding Model**

You can prepare the embedding model according [Prepare Embedding Model](./short_term_memory#prepare-embedding-model).

Here we use the OpenAI Embedding API as an example:

```python
import os
from dbgpt.rag.embedding import DefaultEmbeddingFactory

api_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/embeddings"
api_key = os.getenv("OPENAI_API_KEY")
embeddings = DefaultEmbeddingFactory.openai(api_url=api_url, api_key=api_key)
```
**Prepare Vector Store**

You need to prepare a vector store, here we use the `ChromaStore` as an example:
```python

import shutil
from dbgpt.storage.vector_store.chroma_store import ChromaVectorConfig, ChromaStore

# Delete old vector store directory(/tmp/tmp_ltm_vector_stor)
shutil.rmtree("/tmp/tmp_ltm_vector_store", ignore_errors=True)
vector_store = ChromaStore(
    ChromaVectorConfig(
        embedding_fn=embeddings,
        vector_store_config=ChromaVectorConfig(
            name="ltm_vector_store",
            persist_path="/tmp/tmp_ltm_vector_store",
        ),
    )
)
```

**Create Hybrid Memory**

```python
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from dbgpt.agent import (
    SensoryMemory,
    EnhancedShortTermMemory,
    LongTermMemory,
    HybridMemory,
    AgentMemory,
)

executor = ThreadPoolExecutor()

sensor_memory = SensoryMemory(buffer_size=2)

short_term_memory = EnhancedShortTermMemory(
    embeddings=embeddings,
    buffer_size=2,
    enhance_similarity_threshold=0.7,
    enhance_threshold=3,
    executor=executor,
)

long_term_memory = LongTermMemory(
    executor=ThreadPoolExecutor(), vector_store=vector_store, _default_importance=0.5
)

hybrid_memory = HybridMemory(
    now=datetime.now(),
    sensory_memory=sensor_memory,
    short_term_memory=short_term_memory,
    long_term_memory=long_term_memory,
)

agent_memory: AgentMemory = AgentMemory(memory=hybrid_memory)
```

### Method 3: Creating A Hybrid Memory From Vector Store

You can create a hybrid memory from a vector store, it will use the default values for 
sensory memory and short-term memory.

```python
from dbgpt.agent import HybridMemory, AgentMemory

hybrid_memory = HybridMemory.from_vstore(
    vector_store=vector_store, embeddings=embeddings
)

agent_memory: AgentMemory = AgentMemory(memory=hybrid_memory)
```

## How It Works

When writing a memory fragment:
1. The hybrid memory will store the memory fragments in sensory memory first,
if the sensory memory is full, it will discard all the sensory memory fragments, and 
some of discarded memory fragments will be transferred to short-term memory.
2. Short-term memory will receive some of the sensory memory as outside observations, 
and memory fragments in short-term memory can be enhanced by other observations. Some of 
enhanced memory fragments will be transferred to long-term memory, at the same time, this
enhanced memory will be reflected to higher-level thoughts and insights to the long-term memory.
3. Long-term memory will store the agent's experiences and knowledge. When it receives the memory
fragments from short-term memory, it will compute the importance of the memory fragment, then write
to vector store.

When reading a memory fragment:
1. First, the hybrid memory will read the memory fragments from long-term memory according 
to the observation. The long-term memory uses a `TimeWeightedEmbeddingRetriever` to retrieve 
the memory fragments(latest memory fragments have higher weights).
2. The retrieved memory fragments will be saved to short-term memory(just for enhancing 
the memory fragments, not append a new memory fragment to short-term memory). The retrieved
memory fragments and all short-term memory fragments will be merged, and as the current memory to LLM.
After the enhancing process, there are some new short-term memory fragments will be transferred to long-term memory.