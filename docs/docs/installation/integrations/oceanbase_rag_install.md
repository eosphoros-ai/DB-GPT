# Oceanbase Vector RAG


In this example, we will show how to use the Oceanbase Vector as in DB-GPT RAG Storage. Using a graph database to implement RAG can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.


### Install Dependencies

First, you need to install the `dbgpt Oceanbase Vector storage` library.

```bash
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_obvector" \
--extra "dbgpts"
````

### Prepare Oceanbase Vector

Prepare Oceanbase Vector database service, reference[Oceanbase Vector](https://open.oceanbase.com/) .


### TuGraph Configuration

Set rag storage variables below in `configs/dbgpt-proxy-openai.toml` file, let DB-GPT know how to connect to Oceanbase Vector.

```
[rag.storage]
[rag.storage.vector]
type = "Oceanbase"
uri = "127.0.0.1"
port = "19530"
#username="dbgpt"
#password=19530
```

Then run the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

Optionally, you can also use the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```