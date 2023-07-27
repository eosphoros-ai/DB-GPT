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

1.This project relies on a local MySQL database service, which you need to install locally. We recommend using Docker for installation.
```bash
$ docker run --name=mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=aa12345678 -dit mysql:latest
```
2. prepare server sql script
```bash
$ mysql -h127.0.0.1 -uroot -paa12345678 < ./assets/schema/knowledge_management.sql
```

We use [Chroma embedding database](https://github.com/chroma-core/chroma) as the default for our vector database, so there is no need for special installation. If you choose to connect to other databases, you can follow our tutorial for installation and configuration. 
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

```bash
$ python pilot/server/dbgpt_server.py --light
```

If you want to learn about dbgpt-webui, read https://github.com/csunny/DB-GPT/tree/new-page-framework/datacenter

### 4. Docker (Experimental)

#### 4.1 Building Docker image

```bash
$ bash docker/build_all_images.sh
```

Review images by listing them:

```bash
$ docker images|grep db-gpt
```

Output should look something like the following:

```
db-gpt-allinone    latest     e1ffd20b85ac   45 minutes ago   14.5GB
db-gpt             latest     e36fb0cca5d9   3 hours ago      14GB
```

#### 4.2. Run all in one docker container

**Run with local model**

```bash
$ docker run --gpus "device=0" -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=vicuna-13b \
    -e LANGUAGE=zh \
    -v /data/models:/app/models \
    --name db-gpt-allinone \
    db-gpt-allinone
```

Open http://localhost:5000 with your browser to see the product.


- `-e LLM_MODEL=vicuna-13b`, means we use vicuna-13b as llm model, see /pilot/configs/model_config.LLM_MODEL_CONFIG
- `-v /data/models:/app/models`, means we mount the local model file directory `/data/models` to the docker container directory `/app/models`, please replace it with your model file directory.

You can see log with command:

```bash
$ docker logs db-gpt-allinone -f
```

**Run with openai interface**

```bash
$ PROXY_API_KEY="You api key"
$ PROXY_SERVER_URL="https://api.openai.com/v1/chat/completions"
$ docker run --gpus "device=0" -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=proxyllm \
    -e PROXY_API_KEY=$PROXY_API_KEY \
    -e PROXY_SERVER_URL=$PROXY_SERVER_URL \
    -e LANGUAGE=zh \
    -v /data/models/text2vec-large-chinese:/app/models/text2vec-large-chinese \
    --name db-gpt-allinone \
    db-gpt-allinone
```

- `-e LLM_MODEL=proxyllm`, means we use proxy llm(openai interface, fastchat interface...)
- `-v /data/models/text2vec-large-chinese:/app/models/text2vec-large-chinese`, means we mount the local text2vec model to the docker container.

#### 4.2. Run with docker compose

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
