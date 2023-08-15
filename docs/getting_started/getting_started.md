# Quickstart Guide

This tutorial gives you a quick walkthrough about use DB-GPT with you environment and data.

## Installation

To get started, install DB-GPT with the following steps.

### 1. Hardware Requirements 
As our project has the ability to achieve ChatGPT performance of over 85%, there are certain hardware requirements. However, overall, the project can be deployed and used on consumer-grade graphics cards. The specific hardware requirements for deployment are as follows:

| GPU  | VRAM Size | Performance                                 |
| --------- | --------- | ------------------------------------------- |
| RTX 4090  | 24 GB     | Smooth conversation inference        |
| RTX 3090  | 24 GB     | Smooth conversation inference, better than V100 |
| V100      | 16 GB     | Conversation inference possible, noticeable stutter |

### 2. Install

We use [Chroma embedding database](https://github.com/chroma-core/chroma) as the default for our vector database and use SQLite as the default for our database, so there is no need for special installation. If you choose to connect to other databases, you can follow our tutorial for installation and configuration. 
For the entire installation process of DB-GPT, we use the miniconda3 virtual environment. Create a virtual environment and install the Python dependencies.

```bash
python>=3.10
conda create -n dbgpt_env python=3.10
conda activate dbgpt_env
pip install -r requirements.txt
```
Before use DB-GPT Knowledge Management
```bash
python -m spacy download zh_core_web_sm
```

Once the environment is installed, we have to create a new folder "models" in the DB-GPT project, and then we can put all the models downloaded from huggingface in this directory

```{tip}
Notice make sure you have install git-lfs
```

```bash
git clone https://huggingface.co/lmsys/vicuna-13b-v1.5
git clone https://huggingface.co/Tribbiani/vicuna-13b 
git clone https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
git clone https://huggingface.co/GanymedeNil/text2vec-large-chinese
git clone https://huggingface.co/THUDM/chatglm2-6b
```

The model files are large and will take a long time to download. During the download, let's configure the .env file, which needs to be copied and created from the .env.template

```{tip}
cp .env.template .env
```

You can configure basic parameters in the .env file, for example setting LLM_MODEL to the model to be used

([Vicuna-v1.5](https://huggingface.co/lmsys/vicuna-13b-v1.5) based on llama-2 has been released, we recommend you set `LLM_MODEL=vicuna-13b-v1.5` to try this model)

### 3. Run
You can refer to this document to obtain the Vicuna weights: [Vicuna](https://github.com/lm-sys/FastChat/blob/main/README.md#model-weights) .

If you have difficulty with this step, you can also directly use the model from [this link](https://huggingface.co/Tribbiani/vicuna-7b) as a replacement.

set .env configuration set your vector store type, eg:VECTOR_STORE_TYPE=Chroma, now we support Chroma and Milvus(version > 2.1)


1.Run db-gpt server 

```bash
$ python pilot/server/dbgpt_server.py
```
Open http://localhost:5000 with your browser to see the product.

If you want to access an external LLM service, you need to 1.set the variables LLM_MODEL=YOUR_MODEL_NAME MODEL_SERVER=YOUR_MODEL_SERVER（eg:http://localhost:5000） in the .env file.
2.execute dbgpt_server.py in light mode

If you want to learn about dbgpt-webui, read https://github./csunny/DB-GPT/tree/new-page-framework/datacenter

```bash
$ python pilot/server/dbgpt_server.py --light
```

### 4. Docker (Experimental)

#### 4.1 Building Docker image

```bash
$ bash docker/build_all_images.sh
```

Review images by listing them:

```bash
$ docker images|grep "eosphorosai/dbgpt"
```

Output should look something like the following:

```
eosphorosai/dbgpt-allinone       latest    349d49726588   27 seconds ago       15.1GB
eosphorosai/dbgpt                latest    eb3cdc5b4ead   About a minute ago   14.5GB
```

`eosphorosai/dbgpt` is the base image, which contains the project's base dependencies and a sqlite database. `eosphorosai/dbgpt-allinone` build from `eosphorosai/dbgpt`, which contains a mysql database.

You can pass some parameters to docker/build_all_images.sh.
```bash
$ bash docker/build_all_images.sh \
--base-image nvidia/cuda:11.8.0-devel-ubuntu22.04 \
--pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple \
--language zh
```

You can execute the command `bash docker/build_all_images.sh --help` to see more usage.

#### 4.2. Run all in one docker container

**Run with local model and SQLite database**

```bash
$ docker run --gpus all -d \
    -p 5000:5000 \
    -e LOCAL_DB_TYPE=sqlite \
    -e LOCAL_DB_PATH=data/default_sqlite.db \
    -e LLM_MODEL=vicuna-13b \
    -e LANGUAGE=zh \
    -v /data/models:/app/models \
    --name dbgpt \
    eosphorosai/dbgpt
```

Open http://localhost:5000 with your browser to see the product.


- `-e LLM_MODEL=vicuna-13b`, means we use vicuna-13b as llm model, see /pilot/configs/model_config.LLM_MODEL_CONFIG
- `-v /data/models:/app/models`, means we mount the local model file directory `/data/models` to the docker container directory `/app/models`, please replace it with your model file directory.

You can see log with command:

```bash
$ docker logs dbgpt -f
```

**Run with local model and MySQL database**

```bash
$ docker run --gpus all -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=vicuna-13b \
    -e LANGUAGE=zh \
    -v /data/models:/app/models \
    --name dbgpt \
    eosphorosai/dbgpt-allinone
```

**Run with openai interface**

```bash
$ PROXY_API_KEY="You api key"
$ PROXY_SERVER_URL="https://api.openai.com/v1/chat/completions"
$ docker run --gpus all -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=proxyllm \
    -e PROXY_API_KEY=$PROXY_API_KEY \
    -e PROXY_SERVER_URL=$PROXY_SERVER_URL \
    -e LANGUAGE=zh \
    -v /data/models/text2vec-large-chinese:/app/models/text2vec-large-chinese \
    --name dbgpt \
    eosphorosai/dbgpt-allinone
```

- `-e LLM_MODEL=proxyllm`, means we use proxy llm(openai interface, fastchat interface...)
- `-v /data/models/text2vec-large-chinese:/app/models/text2vec-large-chinese`, means we mount the local text2vec model to the docker container.

#### 4.3. Run with docker compose

```bash
$ docker compose up -d
```

Output should look something like the following:
```
[+] Building 0.0s (0/0)
[+] Running 2/2
 ✔ Container db-gpt-db-1         Started                                                                                                                                                                                          0.4s
 ✔ Container db-gpt-webserver-1  Started
```

You can see log with command:

```bash
$ docker logs db-gpt-webserver-1 -f
```

Open http://localhost:5000 with your browser to see the product.

You can open docker-compose.yml in the project root directory to see more details.


### 5. Multiple GPUs

DB-GPT will use all available gpu by default. And you can modify the setting `CUDA_VISIBLE_DEVICES=0,1` in `.env` file to use the specific gpu IDs.

Optionally, you can also specify the gpu ID to use before the starting command, as shown below:

````shell
# Specify 1 gpu
CUDA_VISIBLE_DEVICES=0 python3 pilot/server/dbgpt_server.py

# Specify 4 gpus
CUDA_VISIBLE_DEVICES=3,4,5,6 python3 pilot/server/dbgpt_server.py
````

You can modify the setting `MAX_GPU_MEMORY=xxGib` in `.env` file to configure the maximum memory used by each GPU.

### 6. Not Enough Memory

DB-GPT supported 8-bit quantization and 4-bit quantization.

You can modify the setting `QUANTIZE_8bit=True` or `QUANTIZE_4bit=True` in `.env` file to use quantization(8-bit quantization is enabled by default).

Llama-2-70b with 8-bit quantization can run with 80 GB of VRAM, and 4-bit quantization can run with 48 GB of VRAM.

Note: you need to install the latest dependencies according to [requirements.txt](https://github.com/eosphoros-ai/DB-GPT/blob/main/requirements.txt).


Here are some of the VRAM size usage of the models we tested in some common scenarios.

| Model     |  Quantize | VRAM Size |
| --------- | --------- | --------- |
| vicuna-7b-v1.5  | 4-bit  | 8 GB     |
| vicuna-7b-v1.5  | 8-bit  | 12 GB     |
| vicuna-13b-v1.5  | 4-bit  | 12 GB     |
| vicuna-13b-v1.5  | 8-bit  | 20 GB     |
| llama-2-7b  | 4-bit  | 8 GB     |
| llama-2-7b  | 8-bit  | 12 GB     |
| llama-2-13b  | 4-bit  | 12 GB     | 
| llama-2-13b  | 8-bit  | 20 GB     |
| llama-2-70b  | 4-bit  | 48 GB     |
| llama-2-70b  | 8-bit  | 80 GB     |
| baichuan-7b  | 4-bit  | 8 GB     |
| baichuan-7b  | 8-bit  | 12 GB     |
| baichuan-13b  | 4-bit  | 12 GB     |
| baichuan-13b  | 8-bit  | 20 GB     |