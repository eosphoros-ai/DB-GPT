---
sidebar_position: 0
---
# Quickstart

DB-GPT supports the installation and use of various open-source and closed-source models. Different models have different requirements for environment and resources. If local model deployment is required, GPU resources are necessary. The API proxy model requires relatively few resources and can be deployed and started on a CPU machine.

:::info note
- Detailed installation and deployment tutorials can be found in [Installation](./installation).
- This page only introduces deployment based on ChatGPT proxy and local GLM model.
:::

## Environment Preparation

### Download Source Code

:::tip
Download DB-GPT
:::

```bash
git clone https://github.com/eosphoros-ai/DB-GPT.git
```

### Environment Setup

- The default database uses SQLite, so there is no need to install a database in the 
default startup mode. If you need to use other databases, please refer to the [advanced tutorials](./application/advanced_tutorial/rag.md) below. 
Starting from version 0.7.0, DB-GPT uses uv for environment and package management, providing faster and more stable dependency management.


:::info note
There are some ways to install uv:
:::

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="uv_sh"
  values={[
    {label: 'Command (macOS And Linux)', value: 'uv_sh'},
    {label: 'PyPI', value: 'uv_pypi'},
    {label: 'Other', value: 'uv_other'},
  ]}>
  <TabItem value="uv_sh" label="Command">
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
  </TabItem>

  <TabItem value="uv_pypi" label="Pypi">
Install uv using pipx.

```bash
python -m pip install --upgrade pip
python -m pip install --upgrade pipx
python -m pipx ensurepath
pipx install uv --global
```
  </TabItem>

  <TabItem value="uv_other" label="Other">

You can see more installation methods on the [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
  </TabItem>

</Tabs>

Then, you can run `uv --version` to check if uv is installed successfully.

```bash
uv --version
```

## Deploy DB-GPT 
:::tip
If you are in the China region, you can add --index-url=https://pypi.tuna.tsinghua.edu.cn/simple at the end of the command.Like this:
```bash
uv sync --all-packages \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts" \
--index-url=https://pypi.tuna.tsinghua.edu.cn/simple
```
This tutorial assumes that you can establish network communication with the dependency download sources.
:::

### Install Dependencies

<Tabs
  defaultValue="openai"
  values={[
    {label: 'OpenAI (proxy)', value: 'openai'},
    {label: 'DeepSeek (proxy)', value: 'deepseek'},
    {label: 'GLM4 (local)', value: 'glm-4'},
    {label: 'VLLM (local)', value: 'vllm'},
    {label: 'LLAMA_CPP (local)', value: 'llama_cpp'},
  ]}>

  <TabItem value="openai" label="OpenAI(proxy)">

```bash
# Use uv to install dependencies needed for OpenAI proxy
uv sync --all-packages --frozen \
--extra "base" \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Run Webserver

To run DB-GPT with OpenAI proxy, you must provide the OpenAI API key in the `configs/dbgpt-proxy-openai.toml` configuration file or privide it in the environment variable with key `OPENAI_API_KEY`.

```toml
# Model Configurations
[models]
[[models.llms]]
...
api_key = "your-openai-api-key"
[[models.embeddings]]
...
api_key = "your-openai-api-key"
```

Then run the following command to start the webserver:

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-openai.toml
```
In the above command, `--config` specifies the configuration file, and `configs/dbgpt-proxy-openai.toml` is the configuration file for the OpenAI proxy model, you can also use other configuration files or create your own configuration file according to your needs.

Optionally, you can also use the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-openai.toml
```

  </TabItem>
<TabItem value="deepseek" label="DeepSeek(proxy)">

```bash
# Use uv to install dependencies needed for OpenAI proxy
uv sync --all-packages --frozen \
--extra "proxy_openai" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "dbgpts"
```

### Run Webserver

To run DB-GPT with DeepSeek proxy, you must provide the DeepSeek API key in the `configs/dbgpt-proxy-deepseek.toml`.

And you can specify your embedding model in the `configs/dbgpt-proxy-deepseek.toml` configuration file, the default embedding model is `BAAI/bge-large-zh-v1.5`. If you want to use other embedding models, you can modify the `configs/dbgpt-proxy-deepseek.toml` configuration file and specify the `name` and `provider` of the embedding model in the `[[models.embeddings]]` section. The provider can be `hf`.

```toml
# Model Configurations
[models]
[[models.llms]]
# name = "deepseek-chat"
name = "deepseek-reasoner"
provider = "proxy/deepseek"
api_key = "your-deepseek-api-key"
[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"
path = "/data/models/bge-large-zh-v1.5"
```

Then run the following command to start the webserver:

```bash
uv run dbgpt start webserver --config configs/dbgpt-proxy-deepseek.toml
```
In the above command, `--config` specifies the configuration file, and `configs/dbgpt-proxy-deepseek.toml` is the configuration file for the DeepSeek proxy model, you can also use other configuration files or create your own configuration file according to your needs.

Optionally, you can also use the following command to start the webserver:
```bash
uv run python packages/dbgpt-app/src/dbgpt_app/dbgpt_server.py --config configs/dbgpt-proxy-deepseek.toml
```

  </TabItem>
  <TabItem value="glm-4" label="GLM4(local)">

```bash
# Use uv to install dependencies needed for GLM4
# Install core dependencies and select desired extensions
uv sync --all-packages --frozen \
--extra "base" \
--extra "hf" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

### Run Webserver

To run DB-GPT with the local model. You can modify the `configs/dbgpt-local-glm.toml` configuration file to specify the model path and other parameters.

```toml
# Model Configurations
[models]
[[models.llms]]
name = "THUDM/glm-4-9b-chat-hf"
provider = "hf"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"
```
In the above configuration file, `[[models.llms]]` specifies the LLM model, and `[[models.embeddings]]` specifies the embedding model. If you not provide the `path` parameter, the model will be downloaded from the Hugging Face model hub according to the `name` parameter.

Then run the following command to start the webserver:

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-glm.toml
```

  </TabItem>
    <TabItem value="vllm" label="VLLM(local)">

```bash
# Use uv to install dependencies needed for vllm
# Install core dependencies and select desired extensions
uv sync --all-packages \
--extra "base" \
--extra "vllm" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

### Run Webserver

To run DB-GPT with the local model. You can modify the `configs/dbgpt-local-vllm.toml` configuration file to specify the model path and other parameters.

```toml
# Model Configurations
[models]
[[models.llms]]
name = "THUDM/glm-4-9b-chat-hf"
provider = "vllm"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"
```
In the above configuration file, `[[models.llms]]` specifies the LLM model, and `[[models.embeddings]]` specifies the embedding model. If you not provide the `path` parameter, the model will be downloaded from the Hugging Face model hub according to the `name` parameter.

Then run the following command to start the webserver:

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-vllm.toml
```

  </TabItem>
      <TabItem value="llama_cpp" label="LLAMA_CPP(local)">

```bash
# Use uv to install dependencies needed for llama-cpp
# Install core dependencies and select desired extensions
uv sync --all-packages \
--extra "base" \
--extra "llama_cpp" \
--extra "rag" \
--extra "storage_chromadb" \
--extra "quant_bnb" \
--extra "dbgpts"
```

### Run Webserver

To run DB-GPT with the local model. You can modify the `configs/dbgpt-local-llama-cpp.toml` configuration file to specify the model path and other parameters.

```toml
# Model Configurations
[models]
[[models.llms]]
name = "DeepSeek-R1-Distill-Qwen-1.5B"
provider = "llama.cpp"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"

[[models.embeddings]]
name = "BAAI/bge-large-zh-v1.5"
provider = "hf"
# If not provided, the model will be downloaded from the Hugging Face model hub
# uncomment the following line to specify the model path in the local file system
# path = "the-model-path-in-the-local-file-system"
```
In the above configuration file, `[[models.llms]]` specifies the LLM model, and `[[models.embeddings]]` specifies the embedding model. If you not provide the `path` parameter, the model will be downloaded from the Hugging Face model hub according to the `name` parameter.

Then run the following command to start the webserver:

```bash
uv run dbgpt start webserver --config configs/dbgpt-local-llama-cpp.toml
```

  </TabItem>
</Tabs>


## Visit Website

Open your browser and visit [`http://localhost:5670`](http://localhost:5670)

### (Optional) Run Web Front-end Separately

You can also run the web front-end separately:

```bash
cd web && npm install
cp .env.template .env
// Set API_BASE_URL to your DB-GPT server address, usually http://localhost:5670
npm run dev
```
Open your browser and visit [`http://localhost:3000`](http://localhost:3000)