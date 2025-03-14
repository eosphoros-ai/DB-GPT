# Postgres

Postgres is a powerful, open source object-relational database system. It is a multi-user database management system and has sophisticated features such as Multi-Version Concurrency Control (MVCC), point in time recovery, tablespaces, asynchronous replication, nested transactions (savepoints), online/hot backups, a sophisticated query planner/optimizer, and write ahead logging for fault tolerance.

In this example, we will show how to use Postgres as in DB-GPT Datasource. Using Postgres to implement Datasource can, to some extent, alleviate the uncertainty and interpretability issues brought about by vector database retrieval.

### Install Dependencies

First, you need to install the `dbgpt postgres datasource` library.

```bash

uv sync --all-packages \
--extra "base" \
--extra "datasource_postgres" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Prepare Postgres

Prepare Postgres database service, reference-[Postgres Installation](https://www.postgresql.org/download/).

Then run the following command to start the webserver:
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

Optionally, you can also use the following command to start the webserver:
```bash

uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

### Postgres Configuration
<p align="left">
  <img src={'https://github.com/user-attachments/assets/affa5ef2-09d6-404c-951e-1220a0dce235'} width="1000px"/>
</p>
