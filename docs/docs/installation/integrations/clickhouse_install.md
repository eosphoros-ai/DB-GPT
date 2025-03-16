# ClickHouse

In this example, we will show how to use the ClickHouse as in DB-GPT Datasource. Using a column-oriented database to implement Datasource can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

### Install Dependencies

First, you need to install the `dbgpt clickhouse datasource` library.

```bash
uv sync --all-packages \
--extra "base" \
--extra "datasource_clickhouse" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Prepare ClickHouse

Prepare ClickHouse database service, reference-[ClickHouse Installation](https://clickhouse.tech/docs/en/getting-started/install/).

Then run the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

Optionally, you can also use the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### ClickHouse Configuration

<p align="left">
  <img src={'https://github.com/user-attachments/assets/b506dc5e-2930-49da-b0c0-5ca051cb6c3f'} width="1000px"/>
</p>

