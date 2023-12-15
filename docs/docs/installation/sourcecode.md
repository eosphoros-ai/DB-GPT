# Source Code Deployment

## Environmental requirements

| Startup Mode         | CPU * MEM    |       GPU      |         Remark  |
|:--------------------:|:------------:|:--------------:|:---------------:|
|     Proxy model          |    4C * 8G      |        None    |  Proxy model does not rely on GPU                         |
|     Local model          |    8C * 32G     |       24G      |  It is best to start locally with a GPU of 24G or above   |






### Download source code

:::tip
Download DB-GPT
:::



```python
git clone https://github.com/eosphoros-ai/DB-GPT.git
```

### Miniconda environment installation

- The default database uses SQLite, so there is no need to install a database in the default startup mode. If you need to use other databases, you can read the [advanced tutorials](/docs/application_manual/advanced_tutorial) below. We recommend installing the Python virtual environment through the conda virtual environment. For the installation of Miniconda environment, please refer to the [Miniconda installation tutorial](https://docs.conda.io/projects/miniconda/en/latest/).

:::tip
Create a Python virtual environment
:::

```python
python >= 3.10
conda create -n dbgpt_env python=3.10
conda activate dbgpt_env

# it will take some minutes
pip install -e ".[default]"
```

:::tip
Copy environment variables
:::
```python
cp .env.template  .env
```


## Model deployment

DB-GPT can be deployed on servers with lower hardware through proxy model, or as a private local model under the GPU environment. If your hardware configuration is low, you can use third-party large language model API services, such as OpenAI, Azure, Qwen, ERNIE Bot, etc.

:::info note

⚠️  You need to ensure that git-lfs is installed
```python
● CentOS installation: yum install git-lfs
● Ubuntu installation: apt-get install git-lfs
● MacOS installation: brew install git-lfs
```
:::
### Proxy model

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs
  defaultValue="openai"
  values={[
    {label: 'Open AI', value: 'openai'},
    {label: 'Qwen', value: 'qwen'},
    {label: 'ChatGLM', value: 'chatglm'},
    {label: 'WenXin', value: 'erniebot'},
  ]}>
  <TabItem value="openai" label="open ai">
  Install dependencies

```python
pip install  -e ".[openai]"
```

Download embedding model

```python
cd DB-GPT
mkdir models and cd models
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
LLM_MODEL=chatgpt_proxyllm
PROXY_API_KEY={your-openai-sk}
PROXY_SERVER_URL=https://api.openai.com/v1/chat/completions
# If you use gpt-4
# PROXYLLM_BACKEND=gpt-4
```
  </TabItem>
  <TabItem value="qwen" label="通义千问">
Install dependencies

```python
pip install dashscope
```

Download embedding model

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
# Aliyun tongyiqianwen
LLM_MODEL=tongyi_proxyllm
TONGYI_PROXY_API_KEY={your-tongyi-sk}
PROXY_SERVER_URL={your_service_url}
```
  </TabItem>
  <TabItem value="chatglm" label="chatglm" >
Install dependencies

```python
pip install zhipuai
```

Download embedding model

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
LLM_MODEL=zhipu_proxyllm
PROXY_SERVER_URL={your_service_url}
ZHIPU_MODEL_VERSION={version}
ZHIPU_PROXY_API_KEY={your-zhipu-sk}
```
  </TabItem>

  <TabItem value="erniebot" label="文心一言" default>

Download embedding model

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large
```

Configure the proxy and modify LLM_MODEL, PROXY_API_URL and API_KEY in the `.env`file

```python
# .env
LLM_MODEL=wenxin_proxyllm
PROXY_SERVER_URL={your_service_url}
WEN_XIN_MODEL_VERSION={version}
WEN_XIN_API_KEY={your-wenxin-sk}
WEN_XIN_API_SECRET={your-wenxin-sct}
```
  </TabItem>
</Tabs>


:::info note

⚠️ Be careful not to overwrite the contents of the `.env` configuration file
:::


### Local model
<Tabs
  defaultValue="vicuna"
  values={[
    {label: 'Vicuna', value: 'vicuna'},
    {label: 'Baichuan', value: 'baichuan'},
    {label: 'ChatGLM', value: 'chatglm'},
  ]}>
  <TabItem value="vicuna" label="vicuna">

##### Hardware requirements description
| Model    		    |   Quantize   |  VRAM Size   	| 
|------------------ |--------------|----------------|
|Vicuna-7b-1.5     	|   4-bit      |  8GB         	|
|Vicuna-7b-1.5 		|   8-bit	   |  12GB        	|
|Vicuna-13b-v1.5   	|   4-bit      |  12GB        	|
|Vicuna-13b-v1.5    |   8-bit      |  24GB          |

##### Download LLM

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large

# llm model, if you use openai or Azure or tongyi llm api service, you don't need to download llm model
git clone https://huggingface.co/lmsys/vicuna-13b-v1.5

```
##### Environment variable configuration, configure the LLM_MODEL parameter in the `.env` file
```python
# .env
LLM_MODEL=vicuna-13b-v1.5
```
  </TabItem>

  <TabItem value="baichuan" label="baichuan">

##### Hardware requirements description
| Model    		    |   Quantize   |  VRAM Size   	| 
|------------------ |--------------|----------------|
|Baichuan-7b     	|   4-bit      |  8GB         	|
|Baichuan-7b  		|   8-bit	   |  12GB          |
|Baichuan-13b     	|   4-bit      |  12GB        	|
|Baichuan-13b       |   8-bit      |  20GB          |

##### Download LLM


```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large

# llm model
git clone https://huggingface.co/baichuan-inc/Baichuan2-7B-Chat
or
git clone https://huggingface.co/baichuan-inc/Baichuan2-13B-Chat

```
##### Environment variable configuration, configure the LLM_MODEL parameter in the `.env` file
```python
# .env
LLM_MODEL=baichuan2-13b
```
  </TabItem>

  <TabItem value="chatglm" label="chatglm">

##### Hardware requirements description
| Model    		    |   Quantize   |  VRAM Size   	| 
|------------------ |--------------|----------------|
|ChatGLM-6b     	|   4-bit      |  7GB         	|
|ChatGLM-6b 	  	|   8-bit	   |  9GB           |
|ChatGLM-6b       	|   FP16       |  14GB        	|


##### Download LLM

```python
cd DB-GPT
mkdir models and cd models

# embedding model
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
or
git clone https://huggingface.co/moka-ai/m3e-large

# llm model
git clone https://huggingface.co/THUDM/chatglm2-6b

```
##### Environment variable configuration, configure the LLM_MODEL parameter in the `.env` file
```python
# .env
LLM_MODEL=chatglm2-6b
```
  </TabItem>

</Tabs>


### llama.cpp(CPU)
:::info note
⚠️ llama.cpp can be run on Mac M1 or Mac M2
:::

DB-GPT also supports the lower-cost inference framework llama.cpp, which can be used through llama-cpp-python.


#### Document preparation
Before using llama.cpp, you first need to prepare the model file in gguf format. There are two ways to obtain it. You can choose one method to obtain the corresponding file.

:::tip
Method 1: Download the converted model
:::

If you want to use [Vicuna-13b-v1.5](https://huggingface.co/lmsys/vicuna-13b-v1.5), you can download the converted file [TheBloke/vicuna-13B-v1.5-GGUF](https://huggingface.co/TheBloke/vicuna-13B-v1.5-GGUF), only this one file is needed. Download the file and put it in the model path. You need to rename the model to: `ggml-model-q4_0.gguf`.
```python
wget https://huggingface.co/TheBloke/vicuna-13B-v1.5-GGUF/resolve/main/vicuna-13b-v1.5.Q4_K_M.gguf -O models/ggml-model-q4_0.gguf
```

:::tip
Method 2: Convert files yourself
:::
During use, you can also convert the model file yourself according to the instructions in [llama.cpp#prepare-data–run](https://github.com/ggerganov/llama.cpp#prepare-data--run), and place the converted file in the models directory and name it `ggml-model-q4_0.gguf`.


#### Install dependencies
llama.cpp is an optional installation item in DB-GPT. You can install it with the following command.

```python
pip install -e ".[llama_cpp]"
```

#### Modify configuration file
Modify the `.env` file to use llama.cpp, and then you can start the service by running the [command](/docs/quickstart.mdx)


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




## Test data (optional)
The DB-GPT project has a part of test data built-in by default, which can be loaded into the local database for testing through the following command
- **Linux**

```python
bash ./scripts/examples/load_examples.sh

```
- **Windows**

```python
.\scripts\examples\load_examples.bat
```

## Run service
The DB-GPT service is packaged into a server, and the entire DB-GPT service can be started through the following command.
```python
python dbgpt/app/dbgpt_server.py
```
:::info NOTE
### Run service

If you are running version v0.4.3 or earlier, please start with the following command:

```python
python pilot/server/dbgpt_server.py
```
:::

## Visit website
Open the browser and visit [`http://localhost:5000`](http://localhost:5000)