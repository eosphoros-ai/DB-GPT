# BM25 RAG

In this example, we will show how to use the Elasticsearch as in DB-GPT RAG Storage. Using a Elasticsearch database to implement RAG can, to some extent, alleviate the uncertainty and interpretability issues brought about by Elasticsearch database retrieval.

### Install Dependencies

First, you need to install the `dbgpt elasticsearch storage` library.

```bash
uv sync --all-packages --frozen \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_elasticsearch" \
--extra "dbgpts"
````

### Prepare Elasticsearch

Prepare Elasticsearch database service, reference-[Elasticsearch Installation](https://www.elastic.co/guide/en/elasticsearch/reference/current/install-elasticsearch.html) .

### Elasticsearch Configuration


Set rag storage variables below in `configs/dbgpt-bm25-rag.toml` file, let DB-GPT know how to connect to Elasticsearch.

```

[rag.storage]
[rag.storage.full_text]
type = "ElasticSearch"
uri = "127.0.0.1"
port = "9200"
```

Then run the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-bm25-rag.toml
```

Optionally
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-bm25-rag.toml
```


## 参见

- [知识库索引原理](/docs/design/kb_index_principles)——一篇文档如何变得可被检索（结构 / 知识图谱含代码图谱 / 向量 / 关键词索引）
- [Agentic RAG 对话原理](/docs/design/agentic_rag_principles)——一个问题如何通过 agentic 检索循环变成带引用的回答
- [RAG 模块参考](/docs/modules/rag)
