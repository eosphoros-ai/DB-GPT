# DuckDB

DuckDB is a high-performance analytical database system. It is designed to execute analytical SQL queries fast and efficiently, and it can also be used as an embedded analytical database.

In this example, we will show how to use DuckDB as in DB-GPT Datasource. Using DuckDB to implement Datasource can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

### Install Dependencies

First, you need to install the `dbgpt duckdb datasource` library.

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_duckdb" \
--extra "rag" \
--extra "storage_chromadb" \

```

### Prepare DuckDB

Prepare DuckDB database service, reference-[DuckDB Installation](https://duckdb.org/docs/installation).

Then run the following command to start the webserver:
```bash

uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml

```

Optionally, you can also use the following command to start the webserver:
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml

```

### DuckDB Configuration
<p align="left">
  <img src={'https://github.com/user-attachments/assets/bc5ffc20-4b5b-4e24-8c29-bf5702b0e840'} width="1000px"/>
</p>