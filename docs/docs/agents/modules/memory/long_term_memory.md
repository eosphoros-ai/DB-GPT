# Long-term Memory

> The short-term memory contains the context information about the agent current situations, 
> while the long-term memory stores the agent past behaviors and thoughts, which can be 
> retrieved according to the current events.

> Long-term memory resembles the external vector storage that agents can rapidly query and retrieve from as needed.

In DB-GPT, the long-term memory stored in the vector storage by default.


## Using Long-term Memory

To use long-term memory, you need to provide a vector store.

### Prepare Embedding Model

First, you need to prepare an embedding model, which is used to convert the text into vectors.
You can prepare the embedding model according [Prepare Embedding Model](./short_term_memory#prepare-embedding-model).

Here we use the OpenAI Embedding API as an example:

```python
import os
from dbgpt.rag.embedding import DefaultEmbeddingFactory

api_url = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1") + "/embeddings"
api_key = os.getenv("OPENAI_API_KEY")
embeddings = DefaultEmbeddingFactory.openai(api_url=api_url, api_key=api_key)
```

### Prepare Vector Store

Then you need to prepare a vector store, here we use the `ChromaStore` as an example,

Install the `chroma` package with the following command:

```bash
pip install chromadb
```

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

### Using Long-term Memory

```python
from concurrent.futures import ThreadPoolExecutor
from dbgpt.agent import AgentMemory, LongTermMemory

# Create an agent memory, which contains a long-term memory
memory = LongTermMemory(
    executor=ThreadPoolExecutor(), vector_store=vector_store, _default_importance=0.5
)
agent_memory: AgentMemory = AgentMemory(memory=memory)
```

In above code, `_default_importance` means the default importance of one memory fragment,
because we use `LongTermMemory` directly, so we need to set the default importance.