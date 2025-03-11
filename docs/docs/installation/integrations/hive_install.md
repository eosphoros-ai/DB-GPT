# Hive

In this example, we will show how to use the Hive as in DB-GPT Datasource. Using Hive to implement Datasource can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

### Install Dependencies

First, you need to install the `dbgpt hive datasource` library.

```bash
uv sync --all-packages \
--extra "base" \
--extra "datasource_hive" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Prepare Hive

Prepare Hive database service, reference-[Hive Installation](https://cwiki.apache.org/confluence/display/Hive/GettingStarted).

Then run the following command to start the webserver:
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

Optionally, you can also use the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### Hive Configuration

<p align="left">
  <img src={'https://github.com/user-attachments/assets/40fb83c5-9b12-496f-8249-c331adceb76f'} width="1000px"/>
</p>

