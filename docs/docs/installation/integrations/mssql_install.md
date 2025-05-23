# MSSQL

In this example, we will show how to use the MSSQL as in DB-GPT Datasource. Using MSSQL to implement Datasource can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

### Install Dependencies

First, you need to install the `dbgpt mssql datasource` library.

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_mssql" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Prepare MSSQL

Prepare MSSQL database service, reference-[MSSQL Installation](https://docs.microsoft.com/en-us/sql/database-engine/install-windows/install-sql-server?view=sql-server-ver15).

Then run the following command to start the webserver:
```bash

uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

Optionally, you can also use the following command to start the webserver:
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### MSSQL Configuration
<p align="left">
  <img src={'https://github.com/user-attachments/assets/2798aaf7-b16f-453e-844a-6ad5dec1d58f'} width="1000px"/>
</p>

