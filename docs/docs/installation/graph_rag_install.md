# Graph RAG Installation


In this example, we will show how to use the Graph RAG framework in DB-GPT. Using a graph database to implement RAG can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

You can refer to the python example file `DB-GPT/examples/rag/graph_rag_example.py` in the source code. This example demonstrates how to load knowledge from a document and store it in a graph store. Subsequently, it recalls knowledge relevant to your question by searching for triplets in the graph store.


### Install Dependencies

First, you need to install the `dbgpt graph_rag` library.

```bash
uv sync --all-packages --frozen \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
--extra "graph_rag"
````

### Prepare Graph Database

To store the knowledge in graph, we need an graph database, [TuGraph](https://github.com/TuGraph-family/tugraph-db) is the first graph database supported by DB-GPT.

Visit github repository of TuGraph to view [Quick Start](https://tugraph-db.readthedocs.io/zh-cn/latest/3.quick-start/1.preparation.html#id5) document, follow the instructions to pull the TuGraph database docker image (latest / version >= 4.5.1) and launch it.

```
docker pull tugraph/tugraph-runtime-centos7:4.5.1
docker run -d -p 7070:7070  -p 7687:7687 -p 9090:9090 --name tugraph_demo tugraph/tugraph-runtime-centos7:latest lgraph_server -d run --enable_plugin true
```

The default port for the bolt protocol is `7687`.

> **Download Tips:**
> 
> There is also a corresponding version of the TuGraph Docker image package on OSS. You can also directly download and import it.
> 
> ```
> wget 'https://tugraph-web.oss-cn-beijing.aliyuncs.com/tugraph/tugraph-4.5.1/tugraph-runtime-centos7-4.5.1.tar' -O tugraph-runtime-centos7-4.5.1.tar
> docker load -i tugraph-runtime-centos7-4.5.1.tar
> ```



### TuGraph Configuration

Set variables below in `configs/dbgpt-graphrag.toml` file, let DB-GPT know how to connect to TuGraph.

```
[rag.storage.graph]
type = "TuGraph"
host="127.0.0.1"
port=7687
username="admin"
password="73@TuGraph"
enable_summary="True"
enable_similarity_search="True"
```

Then run the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-graphrag.toml
```

Optionally, you can also use the following command to start the webserver:
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml




### Load into Knowledge Graph

When using a graph database as the underlying knowledge storage platform, it is necessary to build a knowledge graph to facilitate the archiving and retrieval of documents. DB-GPT leverages the capabilities of large language models to implement an integrated knowledge graph, while still maintaining the flexibility to freely connect to other knowledge graph systems and graph database systems. 

We created a knowledge graph with graph community summaries based on `CommunitySummaryKnowledgeGraph`.



### Chat Knowledge via GraphRAG

> Note: The current test data is in Chinese.

Here we demonstrate how to achieve chat knowledge through Graph RAG on web page.

First, create a knowledge base using the `Knowledge Graph` type. 


<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/create_knowledge_graph.png'} width="1000px"/>
</p>

Then, upload the documents ([graphrag-test.md](https://github.com/eosphoros-ai/DB-GPT/blob/main/examples/test_files/graphrag-test.md)) and process them automatically (markdown header by default).

<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/upload_file.png'} width="1000px"/>
</p>

After indexing, the graph data may look like this.
<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/graph_data.png'} width="1000px"/>
</p>

Start to chat on knowledge graph.
<p align="left">
  <img src={'/img/chat_knowledge/graph_rag/graph_rag_chat.png'} width="1000px"/>
</p>

