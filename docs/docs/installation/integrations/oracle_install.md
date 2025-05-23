# Oracle

In this example, we will show how to use the Oracle as in DB-GPT Datasource. Using Oracle to implement Datasource can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

### Install Dependencies

First, you need to install the `dbgpt oracle datasource` library.

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_oracle" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Prepare Oracle

Prepare Oracle database service, reference-[Oracle Installation](https://docs.oracle.com/en/database/oracle/oracle-database/index.html).

Then run the following command to start the webserver:
```bash

uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```

Optionally, you can also use the following command to start the webserver:
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### Oracle Configuration
<p align="left">
  <img src={'https://github.com/user-attachments/assets/c285f8c3-9e99-4fab-bd39-ae34206ec54f'} width="1000px"/>
</p>
