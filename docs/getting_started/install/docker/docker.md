Docker Install
==================================

### Docker (Experimental)

#### 1. Preparing docker images

**Pull docker image from the [Eosphoros AI Docker Hub](https://hub.docker.com/u/eosphorosai)**

```bash
docker pull eosphorosai/dbgpt:latest
```

**(Optional) Building Docker image**

```bash
bash docker/build_all_images.sh
```

Review images by listing them:

```bash
docker images|grep "eosphorosai/dbgpt"
```

Output should look something like the following:

```
eosphorosai/dbgpt-allinone       latest    349d49726588   27 seconds ago       15.1GB
eosphorosai/dbgpt                latest    eb3cdc5b4ead   About a minute ago   14.5GB
```

`eosphorosai/dbgpt` is the base image, which contains the project's base dependencies and a sqlite database. `eosphorosai/dbgpt-allinone` build from `eosphorosai/dbgpt`, which contains a mysql database.

You can pass some parameters to docker/build_all_images.sh.
```bash
bash docker/build_all_images.sh \
--base-image nvidia/cuda:11.8.0-runtime-ubuntu22.04 \
--pip-index-url https://pypi.tuna.tsinghua.edu.cn/simple \
--language zh
```

You can execute the command `bash docker/build_all_images.sh --help` to see more usage.

#### 2. Run docker container

**Run with local model and SQLite database**

```bash
docker run --gpus all -d \
    -p 5000:5000 \
    -e LOCAL_DB_TYPE=sqlite \
    -e LOCAL_DB_PATH=data/default_sqlite.db \
    -e LLM_MODEL=vicuna-13b-v1.5 \
    -e LANGUAGE=zh \
    -v /data/models:/app/models \
    --name dbgpt \
    eosphorosai/dbgpt
```

Open http://localhost:5000 with your browser to see the product.


- `-e LLM_MODEL=vicuna-13b-v1.5`, means we use vicuna-13b-v1.5 as llm model, see /pilot/configs/model_config.LLM_MODEL_CONFIG
- `-v /data/models:/app/models`, means we mount the local model file directory `/data/models` to the docker container directory `/app/models`, please replace it with your model file directory.

You can see log with command:

```bash
docker logs dbgpt -f
```

**Run with local model and MySQL database**

```bash
docker run --gpus all -d -p 3306:3306 \
    -p 5000:5000 \
    -e LOCAL_DB_HOST=127.0.0.1 \
    -e LOCAL_DB_PASSWORD=aa123456 \
    -e MYSQL_ROOT_PASSWORD=aa123456 \
    -e LLM_MODEL=vicuna-13b-v1.5 \
    -e LANGUAGE=zh \
    -v /data/models:/app/models \
    --name db-gpt-allinone \
    db-gpt-allinone
```

Open http://localhost:5000 with your browser to see the product.


- `-e LLM_MODEL=vicuna-13b-v1.5`, means we use vicuna-13b-v1.5 as llm model, see /pilot/configs/model_config.LLM_MODEL_CONFIG
- `-v /data/models:/app/models`, means we mount the local model file directory `/data/models` to the docker container directory `/app/models`, please replace it with your model file directory.

You can see log with command:

```bash
docker logs db-gpt-allinone -f
```

**Run with openai interface**

```bash
PROXY_API_KEY="You api key"
PROXY_SERVER_URL="https://api.openai.com/v1/chat/completions"
docker run --gpus all -d -p 3306:3306 \
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


Open http://localhost:5000 with your browser to see the product.
