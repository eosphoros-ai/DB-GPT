# Graph RAG User Manual

In this example, we will show how to use the Graph RAG framework in DB-GPT. Using a graph database to implement RAG can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

You can refer to the python example file `DB-GPT/examples/rag/graph_rag_example.py` in the source code. This example demonstrates how to load knowledge from a document and store it in a graph store. Subsequently, it recalls knowledge relevant to your question by searching for triplets in the graph store.


### Install Dependencies

First, you need to install the `dbgpt` library.

```bash
pip install "dbgpt[rag]>=0.5.6"
````

### Prepare Graph Database

To store the knowledge in graph, we need an graph database, [TuGraph](https://github.com/TuGraph-family/tugraph-db) is the first graph database supported by DB-GPT.

Visit github repository of TuGraph to view [Quick Start](https://tugraph-db.readthedocs.io/zh-cn/latest/3.quick-start/1.preparation.html#id5) document, follow the instructions to pull the TuGraph database docker image (latest / version >= 4.3.0) and launch it.

```
docker pull tugraph/tugraph-runtime-centos7:latest
docker run -it -d -p 7001:7001 -p 7070:7070 -p 7687:7687 -p 8000:8000 -p 8888:8888 -p 8889:8889 -p 9090:9090 \
 -v /root/tugraph/data:/var/lib/lgraph/data  -v /root/tugraph/log:/var/log/lgraph_log \
 --name tugraph_demo tugraph/tugraph-runtime-centos7:latest /bin/bash
docker exec -d tugraph_demo bash /setup.sh
```

The default port for the bolt protocol is `7687`, and DB-GPT accesses TuGraph through this port via `neo4j` python client.

```
pip install "neo4j>=5.20.0"
```

### Prepare LLM

To build a Graph RAG program, we need a LLM, here are some of the LLMs that DB-GPT supports:

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI(API)', value: 'openai'},
    {label: 'YI(API)', value: 'yi_proxy'},
    {label: 'API Server(cluster)', value: 'model_service'},
  ]}>
  <TabItem value="openai">

First, you should install the `openai` library. 

```bash
pip install openai
```
Then set your API key in the environment `OPENAI_API_KEY`.

```python
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient()
```
  </TabItem>

  <TabItem value="yi_proxy">

You should have a YI account and get the API key from the YI official website.

First, you should install the `openai` library.

```bash
pip install openai
```

Then set your API key in the environment variable `YI_API_KEY`.

```python
from dbgpt.model.proxy import YiLLMClient

llm_client = YiLLMClient()
```
  </TabItem>

  <TabItem value="model_service">

If you have deployed [DB-GPT cluster](/docs/installation/model_service/cluster) and 
[API server](/docs/installation/advanced_usage/OpenAI_SDK_call)
, you can connect to the API server to get the LLM model.

The API is compatible with the OpenAI API, so you can use the OpenAILLMClient to 
connect to the API server.

First you should install the `openai` library.
```bash
pip install openai
```

```python
from dbgpt.model.proxy import OpenAILLMClient

llm_client = OpenAILLMClient(api_base="http://localhost:8100/api/v1/", api_key="{your_api_key}")
```
  </TabItem>
</Tabs>




### TuGraph Configuration

Set variables below in `.env` file, let DB-GPT know how to connect to TuGraph.

```
GRAPH_STORE_TYPE=TuGraph
TUGRAPH_HOST=127.0.0.1
TUGRAPH_PORT=7687
TUGRAPH_USERNAME=admin
TUGRAPH_PASSWORD=73@TuGraph
```



### Load into Knowledge Graph

When using a graph database as the underlying knowledge storage platform, it is necessary to build a knowledge graph to facilitate the archiving and retrieval of documents. DB-GPT leverages the capabilities of large language models to implement an integrated knowledge graph, while still maintaining the flexibility to freely connect to other knowledge graph systems and graph database systems. 

To maintain compatibility with existing conventional RAG frameworks, we continue to access the knowledge graph through the `VectorStoreConnector` interface. Simply set the `vector_store_type` to `KnowledgeGraph` to enable this connection.

```python
from dbgpt.model.proxy.llms.chatgpt import OpenAILLMClient
from dbgpt.storage.vector_store.base import VectorStoreConfig
from dbgpt.storage.vector_store.connector import VectorStoreConnector

def _create_vector_connector():
    """Create vector connector."""
    return VectorStoreConnector(
        vector_store_type="KnowledgeGraph",
        vector_store_config=VectorStoreConfig(
            name="graph_rag_test_kg",
            embedding_fn=None,
            llm_client=OpenAILLMClient(),
            model_name="gpt-4"
        )
    )
```



### Retrieve from Knowledge Graph

Then you can retrieve the knowledge from the knowledge graph, which is the same with vector store.

```python
import os

from dbgpt.configs.model_config import ROOT_PATH
from dbgpt.rag import ChunkParameters
from dbgpt.rag.assembler import EmbeddingAssembler
from dbgpt.rag.knowledge import KnowledgeFactory

async def main():
    file_path = os.path.join(ROOT_PATH, "examples/test_files/tranformers_story.md")
    knowledge = KnowledgeFactory.from_file_path(file_path)
    vector_connector = _create_kg_connector()
    chunk_parameters = ChunkParameters(chunk_strategy="CHUNK_BY_SIZE")
    # get embedding assembler
    assembler = EmbeddingAssembler.load_from_knowledge(
        knowledge=knowledge,
        chunk_parameters=chunk_parameters,
        vector_store_connector=vector_connector,
    )
    assembler.persist()
    # get embeddings retriever
    retriever = assembler.as_retriever(3)
    chunks = await retriever.aretrieve_with_scores(
        "What actions has Megatron taken?",
        score_threshold=0.3
    )
    print(f"embedding rag example results:{chunks}")
    vector_connector.delete_vector_name("graph_rag_test")
```




### Chat Knowledge via GraphRAG

Here we demonstrate how to achieve chat knowledge through Graph RAG on web page.

First, create a knowledge base using the `Knowledge Graph` type. Upload the knowledge documents and wait for the slicing to complete.


<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/create_knowledge_graph.jpg'} width="1000px"/>
</p>

Then, view the knowledge graph data.
<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/view_graph.jpg'} width="1000px"/>
</p>

The graph data may look like this.
<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/graph_data.jpg'} width="1000px"/>
</p>

Start chat to knowledge based on Graph RAG.
<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/graph_rag_chat.jpg'} width="1000px"/>
</p>
