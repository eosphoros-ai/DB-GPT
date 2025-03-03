# Source Code Deployment

## Environmental requirements

| Startup Mode         | CPU * MEM    |       GPU      |         Remark  |
|:--------------------:|:------------:|:--------------:|:---------------:|
|     Proxy model          |    4C * 8G      |        None    |  Proxy model does not rely on GPU                         |
|     Local model          |    8C * 32G     |       24G      |  It is best to start locally with a GPU of 24G or above   |


## Environment Preparation

### Download Source Code

:::tip
Download DB-GPT
:::

```bash
git clone https://github.com/eosphoros-ai/DB-GPT.git
```

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

### Install Dependencies

<Tabs
  defaultValue="openai"
  values={[
    {label: 'OpenAI (proxy)', value: 'openai'},
    {label: 'DeepSeek (proxy)', value: 'deepseek'},
    {label: 'GLM4 (local)', value: 'glm-4'},
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
--extra "base" \
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


#### More descriptions

| environment variables               | default value    |       description     |
|-------------------------------------|------------------|-----------------------|
| `llama_cpp_prompt_template`         | None             |        Prompt template now supports `zero_shot, vicuna_v1.1,alpaca,llama-2,baichuan-chat,internlm-chat`. If it is None, the model Prompt template can be automatically obtained according to the model path.    |  
|          `llama_cpp_model_path`     |   None           |               model path        | 
|          `llama_cpp_n_gpu_layers`   | 1000000000         |    How many network layers to transfer to the GPU, set this to 1000000000 to transfer all layers to the GPU. If your GPU is low on memory, you can set a lower number, for example: 10.                   | 
|           `llama_cpp_n_threads`     |     None     |      The number of threads to use. If None, the number of threads will be determined automatically.                 | 
|            `llama_cpp_n_batch`      |     512     |         The maximum number of prompt tokens to be batched together when calling llama_eval              | 
|             `llama_cpp_n_gqa`       |     None     |          For the llama-2 70B model, Grouped-query attention must be 8.             | 
|           `llama_cpp_rms_norm_eps`  |     5e-06     |      For the llama-2 model, 5e-6 is a good value.                 | 
|          `llama_cpp_cache_capacity` |     None     |    Maximum model cache size. For example: 2000MiB, 2GiB                   | 
|            `llama_cpp_prefer_cpu`   |     False     |    If a GPU is available, the GPU will be used first by default unless prefer_cpu=False is configured.              | 

## Install DB-GPT Application Database
<Tabs
  defaultValue="sqlite"
  values={[
    {label: 'SQLite', value: 'sqlite'},
    {label: 'MySQL', value: 'mysql'},
  ]}>
<TabItem value="sqlite" label="sqlite">

:::tip NOTE

You do not need to separately create the database tables related to the DB-GPT application in SQLite; 
they will be created automatically for you by default.

:::


 </TabItem>
<TabItem value="mysql" label="MySQL">

:::warning NOTE

After version 0.4.7, we removed the automatic generation of MySQL database Schema for safety.

:::

1. Frist, execute MySQL script to create database and tables.

```bash
$ mysql -h127.0.0.1 -uroot -p{your_password} < ./assets/schema/dbgpt.sql
```

2. Second, set DB-GPT MySQL database settings in `.env` file.

```bash
LOCAL_DB_TYPE=mysql
LOCAL_DB_USER= {your username}
LOCAL_DB_PASSWORD={your_password}
LOCAL_DB_HOST=127.0.0.1
LOCAL_DB_PORT=3306
```

 </TabItem>
</Tabs>


## Test data (optional)
The DB-GPT project has a part of test data built-in by default, which can be loaded into the local database for testing through the following command
- **Linux**

```bash
bash ./scripts/examples/load_examples.sh

```
- **Windows**

```bash
.\scripts\examples\load_examples.bat
```

:::

## Visit website
Open the browser and visit [`http://localhost:5670`](http://localhost:5670)