---
sidebar_position: 1
---

# CLI Quick Start

Install DB-GPT from PyPI and start it with a single command — no source checkout required.

:::tip Prerequisites
- Python **3.10** or later
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager (recommended) or pip
:::

## 1. Install

```bash
# Recommended: use uv
uv pip install dbgpt-app

# Or with pip
pip install dbgpt-app
```

:::tip Using a PyPI Mirror
For faster downloads, specify a mirror when installing:

```bash
uv pip install dbgpt-app --index-url https://pypi.tuna.tsinghua.edu.cn/simple  # uv

pip install dbgpt-app -i https://pypi.tuna.tsinghua.edu.cn/simple              # pip
```

Alternatively, set an environment variable to apply the mirror to **all** installs in the current shell session:

```bash
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple   # uv

export PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple  # pip
```
:::

:::info What's included
The default installation includes the **core framework** (CLI, FastAPI, SQLAlchemy, Agent),
**OpenAI-compatible LLM support** (also works with Kimi, Qwen, MiniMax, Z.AI),
**DashScope / Tongyi** support, **RAG document parsing**, and **ChromaDB** vector store.

Need additional providers or data sources? See [Optional Modules](#8-optional-modules).
:::

After installation the `dbgpt` command is available in your terminal.

## 2. Start DB-GPT

```bash
dbgpt start
```

That's it! On first run DB-GPT will launch an **interactive setup wizard** that helps you:

1. Choose an LLM provider (OpenAI, Kimi, Qwen, MiniMax, Z.AI, or a custom endpoint)
2. Enter your API key (or use an environment variable)
3. Confirm the model names and API base URL

Once complete, a TOML configuration file is written to `~/.dbgpt/configs/<profile>.toml` and the web server starts automatically.

### What the startup looks like

```
    ____  ____        ____ ____ _____
   |  _ \| __ )      / ___|  _ \_   _|
   | | | |  _ \ ____| |  _| |_) || |
   | |_| | |_) |____| |_| |  __/ | |
   |____/|____/      \____|_|    |_|

   🚀 DB-GPT Quick Start

   +- - - - - - - - - - - - - - - - - - - - - - - -+
   :  Profile:   openai                              :
   :  Config:    /Users/you/.dbgpt/configs/openai.toml:
   :  Workspace: /Users/you/.dbgpt/workspace          :
   +- - - - - - - - - - - - - - - - - - - - - - - -+
```

## 3. Open the Web UI

Then open [http://localhost:5670](http://localhost:5670).

---

## 4. Command Reference

### Overview

```
dbgpt [OPTIONS] COMMAND [ARGS]...

Options:
  --log-level TEXT   Log level (default: warn)
  --version          Show version and exit
  --help             Show help message

Commands:
  start     Start the DB-GPT server
  stop      Stop a running server
  setup     Configure LLM provider (interactive wizard or CI mode)
  profile   Manage configuration profiles
  knowledge Knowledge base operations
  model     Manage model serving
  db        Database management and migration
  ...
```

---

### `dbgpt start`

Start the DB-GPT web server. Running `dbgpt start` without a subcommand is equivalent to `dbgpt start web`.

#### Subcommands

| Subcommand | Description |
|---|---|
| `web` (or `webserver`) | Start the web server (default) |
| `none` | API-only mode — *planned for a future release* |
| `controller` | Start the model controller |
| `worker` | Start a model worker |
| `apiserver` | Start the API server |

#### `dbgpt start web` Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--config` | `-c` | PATH | *auto* | Path to a TOML config file. If omitted, uses the active profile or launches the setup wizard. |
| `--profile` | `-p` | TEXT | *active* | Provider profile name (`openai`, `kimi`, `qwen`, `minimax`, `glm`, `custom`). Overrides the active profile. |
| `--yes` | `-y` | FLAG | false | Non-interactive mode: skip the wizard and use defaults / environment variables. Ideal for CI/CD. |
| `--api-key` | | TEXT | *env* | API key for the chosen provider. Can also be set via the provider's own environment variable. |
| `--daemon` | `-d` | FLAG | false | Run as a background daemon. Stop with `dbgpt stop webserver`. |

#### Examples

```bash
# Interactive (first run) — wizard will guide you
dbgpt start

# Use an existing profile
dbgpt start web --profile openai

# Non-interactive with explicit API key
dbgpt start web --profile kimi --api-key sk-xxx --yes

# Use a specific config file
dbgpt start web --config /path/to/my-config.toml

# Run as a daemon
dbgpt start web --daemon
```

#### Config Resolution Priority

When the web server starts, the configuration file is resolved in this order:

1. **`--config` flag** — if specified, use this file directly
2. **`--profile` flag** — look up `~/.dbgpt/configs/<profile>.toml`
3. **Active profile** — read from `~/.dbgpt/config.toml`
4. **Setup wizard** — if nothing is configured yet, launch the interactive wizard

---

### `dbgpt stop`

Stop running DB-GPT server processes.

```bash
# Stop the web server
dbgpt stop webserver

# Stop the web server on a specific port
dbgpt stop webserver --port 5670

# Stop all servers
dbgpt stop all
```

---

### `dbgpt setup`

Configure the LLM provider interactively, or in non-interactive / CI mode. This command writes a TOML config to `~/.dbgpt/configs/<profile>.toml` and marks it as the active profile.

#### Options

| Option | Short | Type | Default | Description |
|---|---|---|---|---|
| `--profile` | `-p` | TEXT | *interactive* | Provider profile to configure. If omitted, an interactive menu is shown. |
| `--yes` | `-y` | FLAG | false | Non-interactive mode: skip the wizard and use defaults. |
| `--api-key` | | TEXT | *env* | API key. Also reads `DBGPT_API_KEY` env var. |
| `--show` | | FLAG | false | Show the current active profile and config path, then exit. |

#### Examples

```bash
# Interactive wizard
dbgpt setup

# Non-interactive: use OpenAI with env key
export OPENAI_API_KEY=sk-xxx
dbgpt setup --profile openai --yes

# Non-interactive with explicit key
dbgpt setup --profile kimi --api-key sk-xxx

# Show current configuration
dbgpt setup --show
```

---

### `dbgpt profile`

Manage multiple configuration profiles. Each profile is a TOML file under `~/.dbgpt/configs/`.

#### Subcommands

| Subcommand | Description |
|---|---|
| `list` | List all profiles. The active one is marked with `*`. |
| `show <name>` | Display the TOML content of a profile. |
| `create <name>` | Create (or reconfigure) a profile using the setup wizard. |
| `switch <name>` | Set a profile as the active default. |
| `delete <name>` | Delete a profile configuration file. |

#### Examples

```bash
# List all profiles
dbgpt profile list
#   openai     ← no asterisk
# * kimi       ← active

# Show profile content
dbgpt profile show openai

# Create a new profile
dbgpt profile create qwen

# Switch active profile
dbgpt profile switch openai

# Delete a profile
dbgpt profile delete minimax
dbgpt profile delete minimax --yes  # skip confirmation
```

---

## 5. Supported Providers

The setup wizard and `--profile` flag support the following providers:

| Profile Name | Display Name | LLM Model | Embedding Model | API Key Env Var |
|---|---|---|---|---|
| `openai` | OpenAI | gpt-4o | text-embedding-3-small | `OPENAI_API_KEY` |
| `kimi` | Kimi | kimi-k2 | text-embedding-v3 | `MOONSHOT_API_KEY` (+ `DASHSCOPE_API_KEY` for embeddings) |
| `qwen` | Qwen | qwen-plus | text-embedding-v3 | `DASHSCOPE_API_KEY` |
| `minimax` | MiniMax | abab6.5s-chat | embo-01 | `MINIMAX_API_KEY` |
| `glm` | Z.AI | glm-4-plus | embedding-3 | `ZHIPUAI_API_KEY` |
| `custom` | Custom | gpt-4o | text-embedding-3-small | `OPENAI_API_KEY` |

:::info
The **Custom** profile lets you connect to any OpenAI-compatible API endpoint. During the wizard you'll be asked for the API base URL.
:::

---

## 6. Directory Structure

After first run, DB-GPT creates the following structure under your home directory:

```
~/.dbgpt/
├── config.toml              # Records the active profile name
├── configs/
│   ├── openai.toml          # Profile: OpenAI
│   ├── kimi.toml            # Profile: Kimi
│   └── ...                  # One file per profile
└── workspace/
    └── pilot/               # Runtime workspace (databases, data files, etc.)
        ├── meta_data/
        │   └── dbgpt.db     # SQLite metadata database
        └── data/             # Vector store data
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DBGPT_HOME` | `~/.dbgpt` | Override the DB-GPT home directory |
| `OPENAI_API_KEY` | — | OpenAI API key (used by `openai` and `custom` profiles) |
| `MOONSHOT_API_KEY` | — | Kimi / Moonshot API key |
| `DASHSCOPE_API_KEY` | — | Qwen / DashScope API key (also used for Kimi embeddings) |
| `MINIMAX_API_KEY` | — | MiniMax API key |
| `ZHIPUAI_API_KEY` | — | Z.AI / Zhipu API key |
| `DBGPT_API_KEY` | — | Generic API key (fallback for `--api-key` flag) |
| `DBGPT_LANG` | `en` | UI language (`en` or `zh`) |

---

## 7. Common Workflows

### First-time setup

```bash
pip install dbgpt-app
dbgpt start
# Follow the wizard → choose provider → enter API key → server starts
```

### Switch between providers

```bash
# Create a Kimi profile
dbgpt profile create kimi

# Switch to it
dbgpt profile switch kimi

# Start with the new profile
dbgpt start
```

### CI/CD deployment

```bash
export OPENAI_API_KEY=sk-xxx
dbgpt setup --profile openai --yes
dbgpt start web --daemon
```

### Custom endpoint (e.g. Azure OpenAI, local vLLM)

```bash
dbgpt setup --profile custom
# Wizard will ask for:
#   - API base URL (e.g. http://localhost:8000/v1)
#   - API key
#   - Model names
```

---

## 8. Optional Modules

The core framework is included by default when you `pip install dbgpt-app`. Use extras to add LLM providers, vector stores, data sources, and more.

### LLM Providers

| Extra | Provider | Key packages |
|-------|----------|-------------|
| `proxy_openai` | OpenAI, Kimi, Qwen, MiniMax, Z.AI, any OpenAI-compatible API | `openai`, `tiktoken` |
| `proxy_ollama` | Ollama (local models) | `ollama` |
| `proxy_zhipuai` | Zhipu AI (GLM) | `openai` |
| `proxy_tongyi` | Tongyi Qianwen | `openai`, `dashscope` |
| `proxy_qianfan` | Baidu Qianfan | `qianfan` |
| `proxy_anthropic` | Anthropic Claude | `anthropic` |

### Vector Stores

| Extra | Storage | Key packages |
|-------|---------|-------------|
| `storage_chromadb` | ChromaDB | `chromadb`, `onnxruntime` |
| `storage_milvus` | Milvus | `pymilvus` |
| `storage_valkey` | Valkey | `valkey-glide` |
| `storage_weaviate` | Weaviate | `weaviate-client` |
| `storage_elasticsearch` | Elasticsearch | `elasticsearch` |
| `storage_obvector` | OBVector | `pyobvector` |

### Knowledge & RAG

| Extra | What it adds | Key packages |
|-------|-------------|-------------|
| `rag` | Document parsing (PDF, DOCX, PPTX, Markdown, HTML) | `spacy`, `pypdf`, `python-docx`, `python-pptx` |
| `graph_rag` | Graph-based RAG with TuGraph/Neo4j | `networkx`, `neo4j` |

### Data Sources

| Extra | Database | Key packages |
|-------|----------|-------------|
| `datasource_mysql` | MySQL | `mysqlclient` |
| `datasource_postgres` | PostgreSQL | `psycopg2-binary` |
| `datasource_clickhouse` | ClickHouse | `clickhouse-connect` |
| `datasource_oracle` | Oracle | `oracledb` |
| `datasource_mssql` | SQL Server | `pymssql` |
| `datasource_spark` | Apache Spark | `pyspark` |
| `datasource_hive` | Hive | `pyhive` |
| `datasource_vertica` | Vertica | `vertica-python` |

### Example: combine multiple extras

```bash
# OpenAI + ChromaDB + RAG + MySQL
pip install "dbgpt-app[proxy_openai,storage_chromadb,rag,datasource_mysql]"
```

:::tip Minimal install
If you only need the core framework without any LLM or storage:
```bash
pip install dbgpt-app
```
This gives you the CLI, FastAPI server, and agent framework — but you'll need to add at least one LLM provider extra to actually use it.
:::

---

## 9. Troubleshooting

### Port already in use

```bash
# Stop the existing server
dbgpt stop webserver --port 5670

# Or choose a different port by editing the config file
# [service.web]
# port = 5671
```

### "No config file found" error

This means no profile has been set up yet. Run:

```bash
dbgpt setup
```

### Changing your API key

Re-run the setup wizard for the same profile — it will overwrite the existing config:

```bash
dbgpt setup --profile openai
# Or simply edit ~/.dbgpt/configs/openai.toml directly
```

### View current configuration

```bash
dbgpt setup --show
dbgpt profile show openai
```
